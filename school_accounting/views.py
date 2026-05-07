from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import (
    SchoolExpenseCategory, SchoolExpense, TeacherSalary,
    SchoolIncome, SchoolDebt, SchoolAsset, SalaryReceipt
)
from .serializers import (
    SchoolExpenseCategorySerializer, SchoolExpenseSerializer,
    TeacherSalarySerializer, SchoolIncomeSerializer,
    SchoolDebtSerializer, SchoolAssetSerializer, SalaryReceiptSerializer
)
from fees.models import FeePayment


def _get_tenant(user):
    """Resolve tenant from user — handles admin, worker, and tenant FK."""
    # 1. Direct FK on user model
    tenant = getattr(user, 'tenant', None)
    if tenant:
        return tenant
    # 2. User is the tenant admin
    from tenants.models import Tenant as T
    tenant = T.objects.filter(admin=user).first()
    if tenant:
        return tenant
    # 3. User is a worker linked to a tenant
    worker = getattr(user, 'worker_profile', None)
    if worker:
        return worker.tenant
    # 4. TenantMembership fallback
    membership = user.tenants_memberships.select_related('tenant').first()
    if membership:
        return membership.tenant
    return None


def _require_tenant(user):
    tenant = _get_tenant(user)
    if not tenant:
        raise PermissionDenied('No tenant associated with this account.')
    return tenant


class SchoolExpenseCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = SchoolExpenseCategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = _get_tenant(self.request.user)
        if not tenant:
            return SchoolExpenseCategory.objects.none()
        return SchoolExpenseCategory.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=_require_tenant(self.request.user))


class SchoolExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = SchoolExpenseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = _get_tenant(self.request.user)
        if not tenant:
            return SchoolExpense.objects.none()
        qs = SchoolExpense.objects.filter(tenant=tenant)
        p = self.request.query_params
        if p.get('date_from'):
            qs = qs.filter(date__gte=p['date_from'])
        if p.get('date_to'):
            qs = qs.filter(date__lte=p['date_to'])
        if p.get('category'):
            qs = qs.filter(category_id=p['category'])
        if p.get('term'):
            qs = qs.filter(term=p['term'])
        if p.get('academic_year'):
            qs = qs.filter(academic_year=p['academic_year'])
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=_require_tenant(self.request.user), created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        expenses = self.get_queryset()
        total = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # This month
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        this_month = expenses.filter(date__gte=month_start).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # By category
        by_category = expenses.values('category__name', 'category__category_type').annotate(
            total=Sum('amount'), count=Count('id')
        ).order_by('-total')
        
        # Trend (last 12 months)
        twelve_months_ago = now.date() - timedelta(days=365)
        trend = []
        for i in range(12):
            ms = twelve_months_ago + timedelta(days=30 * i)
            me = ms + timedelta(days=30)
            mt = expenses.filter(date__gte=ms, date__lt=me).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            trend.append({'month': ms.strftime('%b %Y'), 'total': float(mt)})
        
        return Response({
            'total_expenses': float(total),
            'this_month': float(this_month),
            'by_category': list(by_category),
            'trend': trend,
            'expense_count': expenses.count(),
        })


class TeacherSalaryViewSet(viewsets.ModelViewSet):
    serializer_class = TeacherSalarySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = _get_tenant(self.request.user)
        if not tenant:
            return TeacherSalary.objects.none()
        qs = TeacherSalary.objects.filter(tenant=tenant)
        p = self.request.query_params
        if p.get('status'):
            qs = qs.filter(status=p['status'])
        if p.get('month'):
            qs = qs.filter(month=p['month'])
        if p.get('teacher_name'):
            qs = qs.filter(teacher_name__icontains=p['teacher_name'])
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=_require_tenant(self.request.user), created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        salaries = self.get_queryset()
        
        total_paid = salaries.filter(status='paid').aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')
        total_pending = salaries.filter(status__in=['pending', 'partial']).aggregate(
            total=Sum('net_salary')
        )['total'] or Decimal('0')
        amount_paid_partial = salaries.filter(status='partial').aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')
        balance_due = total_pending - amount_paid_partial
        
        # This month
        now = timezone.now()
        month_start = now.replace(day=1)
        this_month_paid = salaries.filter(payment_date__gte=month_start, status='paid').aggregate(
            total=Sum('amount_paid')
        )['total'] or Decimal('0')
        
        # By status
        by_status = salaries.values('status').annotate(count=Count('id'), total=Sum('net_salary'))
        
        # Trend (last 12 months)
        twelve_months_ago = now.date() - timedelta(days=365)
        trend = []
        for i in range(12):
            ms = twelve_months_ago + timedelta(days=30 * i)
            me = ms + timedelta(days=30)
            mt = salaries.filter(month__gte=ms, month__lt=me, status='paid').aggregate(
                total=Sum('amount_paid')
            )['total'] or Decimal('0')
            trend.append({'month': ms.strftime('%b %Y'), 'total': float(mt)})
        
        return Response({
            'total_paid': float(total_paid),
            'total_pending': float(total_pending),
            'balance_due': float(balance_due),
            'this_month_paid': float(this_month_paid),
            'by_status': list(by_status),
            'trend': trend,
            'teacher_count': salaries.values('teacher_name').distinct().count(),
        })


    @action(detail=True, methods=['post'])
    def generate_receipt(self, request, pk=None):
        """Generate (or retrieve existing) receipt for a salary payment."""
        salary = self.get_object()
        tenant = _require_tenant(request.user)

        # Return existing receipt if already generated for this salary
        existing = SalaryReceipt.objects.filter(salary=salary).first()
        if existing:
            return Response(SalaryReceiptSerializer(existing).data)

        # Build unique receipt number: SAL-{tenant_id}-{salary_id}-{YYYYMM}
        month_str = salary.month.strftime('%Y%m') if salary.month else 'XXXXXX'
        receipt_number = f"SAL-{tenant.id}-{str(salary.id).zfill(4)}-{month_str}"

        receipt = SalaryReceipt.objects.create(
            tenant=tenant,
            salary=salary,
            receipt_number=receipt_number,
            issued_by=request.user,
            notes=request.data.get('notes', ''),
        )
        return Response(SalaryReceiptSerializer(receipt).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def receipt(self, request, pk=None):
        """Retrieve existing receipt for a salary, or 404 if not yet generated."""
        salary = self.get_object()
        receipt = SalaryReceipt.objects.filter(salary=salary).first()
        if not receipt:
            return Response({'detail': 'No receipt generated yet.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(SalaryReceiptSerializer(receipt).data)


class SalaryReceiptViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve all salary receipts for the tenant."""
    serializer_class = SalaryReceiptSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = _get_tenant(self.request.user)
        if not tenant:
            return SalaryReceipt.objects.none()
        qs = SalaryReceipt.objects.filter(tenant=tenant).select_related('salary', 'issued_by')
        p = self.request.query_params
        if p.get('teacher_name'):
            qs = qs.filter(salary__teacher_name__icontains=p['teacher_name'])
        if p.get('month'):
            qs = qs.filter(salary__month=p['month'])
        return qs


class SchoolIncomeViewSet(viewsets.ModelViewSet):
    serializer_class = SchoolIncomeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = _get_tenant(self.request.user)
        if not tenant:
            return SchoolIncome.objects.none()
        qs = SchoolIncome.objects.filter(tenant=tenant)
        p = self.request.query_params
        if p.get('date_from'):
            qs = qs.filter(date__gte=p['date_from'])
        if p.get('date_to'):
            qs = qs.filter(date__lte=p['date_to'])
        if p.get('income_type'):
            qs = qs.filter(income_type=p['income_type'])
        if p.get('term'):
            qs = qs.filter(term=p['term'])
        if p.get('academic_year'):
            qs = qs.filter(academic_year=p['academic_year'])
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=_require_tenant(self.request.user), created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        income = self.get_queryset()
        total = income.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # This month
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        this_month = income.filter(date__gte=month_start).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # By type
        by_type = income.values('income_type').annotate(total=Sum('amount'), count=Count('id')).order_by('-total')
        
        # Trend (last 12 months)
        twelve_months_ago = now.date() - timedelta(days=365)
        trend = []
        for i in range(12):
            ms = twelve_months_ago + timedelta(days=30 * i)
            me = ms + timedelta(days=30)
            mt = income.filter(date__gte=ms, date__lt=me).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            trend.append({'month': ms.strftime('%b %Y'), 'total': float(mt)})
        
        return Response({
            'total_income': float(total),
            'this_month': float(this_month),
            'by_type': list(by_type),
            'trend': trend,
            'income_count': income.count(),
        })


class SchoolDebtViewSet(viewsets.ModelViewSet):
    serializer_class = SchoolDebtSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = _get_tenant(self.request.user)
        if not tenant:
            return SchoolDebt.objects.none()
        qs = SchoolDebt.objects.filter(tenant=tenant)
        p = self.request.query_params
        if p.get('status'):
            qs = qs.filter(status=p['status'])
        if p.get('debt_type'):
            qs = qs.filter(debt_type=p['debt_type'])
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=_require_tenant(self.request.user), created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        debts = self.get_queryset()
        
        total_debt = debts.aggregate(total=Sum('original_amount'))['total'] or Decimal('0')
        total_paid = debts.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')
        total_balance = debts.aggregate(total=Sum('balance'))['total'] or Decimal('0')
        
        # By status
        by_status = debts.values('status').annotate(count=Count('id'), total=Sum('balance'))
        
        # By type
        by_type = debts.values('debt_type').annotate(total=Sum('balance'), count=Count('id')).order_by('-total')
        
        # Overdue
        overdue = debts.filter(status='overdue')
        overdue_count = overdue.count()
        overdue_amount = overdue.aggregate(total=Sum('balance'))['total'] or Decimal('0')
        
        return Response({
            'total_debt': float(total_debt),
            'total_paid': float(total_paid),
            'total_balance': float(total_balance),
            'overdue_count': overdue_count,
            'overdue_amount': float(overdue_amount),
            'by_status': list(by_status),
            'by_type': list(by_type),
            'debt_count': debts.count(),
        })


class SchoolAssetViewSet(viewsets.ModelViewSet):
    serializer_class = SchoolAssetSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = _get_tenant(self.request.user)
        if not tenant:
            return SchoolAsset.objects.none()
        qs = SchoolAsset.objects.filter(tenant=tenant)
        p = self.request.query_params
        if p.get('asset_type'):
            qs = qs.filter(asset_type=p['asset_type'])
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=_require_tenant(self.request.user))

    @action(detail=False, methods=['get'])
    def summary(self, request):
        assets = self.get_queryset()
        
        total_purchase_value = assets.aggregate(total=Sum('purchase_value'))['total'] or Decimal('0')
        total_current_value = assets.aggregate(total=Sum('current_value'))['total'] or Decimal('0')
        
        # By type
        by_type = assets.values('asset_type').annotate(
            total_value=Sum('current_value'), count=Count('id')
        ).order_by('-total_value')
        
        return Response({
            'total_purchase_value': float(total_purchase_value),
            'total_current_value': float(total_current_value),
            'depreciation': float(total_purchase_value - total_current_value),
            'by_type': list(by_type),
            'asset_count': assets.count(),
        })


class SchoolProfitLossViewSet(viewsets.ViewSet):
    """Profit & Loss statement for schools"""
    permission_classes = [IsAuthenticated]

    def list(self, request):
        tenant = _get_tenant(request.user)
        if not tenant:
            return Response({'error': 'No tenant found.'}, status=status.HTTP_403_FORBIDDEN)

        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if not date_from or not date_to:
            date_to = timezone.now().date()
            date_from = date_to.replace(month=1, day=1)

        # Income
        fee_income = FeePayment.objects.filter(
            tenant=tenant, payment_date__gte=date_from, payment_date__lte=date_to
        ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')
        
        other_income = SchoolIncome.objects.filter(
            tenant=tenant, date__gte=date_from, date__lte=date_to
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        total_income = fee_income + other_income

        # Expenses
        expenses = SchoolExpense.objects.filter(
            tenant=tenant, date__gte=date_from, date__lte=date_to
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        teacher_salaries = TeacherSalary.objects.filter(
            tenant=tenant, month__gte=date_from, month__lte=date_to, status='paid'
        ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')
        
        total_expenses = expenses + teacher_salaries

        # Profit
        net_profit = total_income - total_expenses
        profit_margin = (net_profit / total_income * 100) if total_income > 0 else 0

        # Expense breakdown
        expense_by_category = SchoolExpense.objects.filter(
            tenant=tenant, date__gte=date_from, date__lte=date_to
        ).values('category__name', 'category__category_type').annotate(
            total=Sum('amount')
        ).order_by('-total')

        return Response({
            'period': {'start': date_from, 'end': date_to},
            'income': {
                'fee_income': float(fee_income),
                'other_income': float(other_income),
                'total': float(total_income),
            },
            'expenses': {
                'general_expenses': float(expenses),
                'teacher_salaries': float(teacher_salaries),
                'total': float(total_expenses),
            },
            'expense_breakdown': list(expense_by_category),
            'net_profit': float(net_profit),
            'profit_margin': float(profit_margin),
        })


class SchoolBalanceSheetViewSet(viewsets.ViewSet):
    """Balance sheet for schools"""
    permission_classes = [IsAuthenticated]

    def list(self, request):
        tenant = _get_tenant(request.user)
        if not tenant:
            return Response({'error': 'No tenant found.'}, status=status.HTTP_403_FORBIDDEN)

        # Assets
        assets = SchoolAsset.objects.filter(tenant=tenant)
        total_assets = assets.aggregate(total=Sum('current_value'))['total'] or Decimal('0')
        assets_by_type = assets.values('asset_type').annotate(total=Sum('current_value'))

        # Liabilities (Debts)
        debts = SchoolDebt.objects.filter(tenant=tenant, status__in=['active', 'partial', 'overdue'])
        total_liabilities = debts.aggregate(total=Sum('balance'))['total'] or Decimal('0')
        liabilities_by_type = debts.values('debt_type').annotate(total=Sum('balance'))

        # Equity (Assets - Liabilities)
        total_equity = total_assets - total_liabilities

        return Response({
            'assets': {
                'total': float(total_assets),
                'by_type': list(assets_by_type),
            },
            'liabilities': {
                'total': float(total_liabilities),
                'by_type': list(liabilities_by_type),
            },
            'equity': {
                'total': float(total_equity),
            },
            'total_liabilities_and_equity': float(total_liabilities + total_equity),
            'is_balanced': abs(total_assets - (total_liabilities + total_equity)) < Decimal('0.01'),
        })
