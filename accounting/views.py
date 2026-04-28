from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import (
    ExpenseCategory, Expense, Payment, Tax,
    Asset, Liability, Equity, AuditLog
)
from .serializers import (
    ExpenseCategorySerializer, ExpenseSerializer, PaymentSerializer,
    TaxSerializer, AssetSerializer, LiabilitySerializer, EquitySerializer,
    AuditLogSerializer
)
from core.models import Order


def _get_tenant(user):
    """Resolve tenant from user FK, falling back to admin lookup."""
    tenant = getattr(user, 'tenant', None)
    if not tenant:
        from tenants.models import Tenant as T
        tenant = T.objects.filter(admin=user).first()
        if tenant:
            user.tenant = tenant
            user.save(update_fields=['tenant'])
    return tenant


def _require_tenant(user):
    tenant = _get_tenant(user)
    if not tenant:
        raise PermissionDenied('No tenant associated with this account.')
    return tenant


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseCategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = _get_tenant(self.request.user)
        if not tenant:
            return ExpenseCategory.objects.none()
        return ExpenseCategory.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=_require_tenant(self.request.user))


class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = _get_tenant(self.request.user)
        if not tenant:
            return Expense.objects.none()
        qs = Expense.objects.filter(tenant=tenant)
        p = self.request.query_params
        if p.get('date_from'):
            qs = qs.filter(date__gte=p['date_from'])
        if p.get('date_to'):
            qs = qs.filter(date__lte=p['date_to'])
        if p.get('category'):
            qs = qs.filter(category_id=p['category'])
        if p.get('vendor'):
            qs = qs.filter(vendor__icontains=p['vendor'])
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=_require_tenant(self.request.user), created_by=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        old = {'vendor': instance.vendor, 'amount': str(instance.amount),
               'category': instance.category.name if instance.category else None,
               'payment_method': instance.payment_method, 'date': str(instance.date)}
        updated = serializer.save(updated_by=self.request.user)
        new = {'vendor': updated.vendor, 'amount': str(updated.amount),
               'category': updated.category.name if updated.category else None,
               'payment_method': updated.payment_method, 'date': str(updated.date)}
        AuditLog.objects.create(
            tenant=_require_tenant(self.request.user), user=self.request.user,
            action='update', model_type='expense', object_id=updated.id,
            object_repr=f"Expense: {updated.vendor}", changes={'before': old, 'after': new},
            ip_address=self._get_ip(), user_agent=self.request.META.get('HTTP_USER_AGENT', '')[:500],
            endpoint=self.request.path, method=self.request.method,
        )

    def perform_destroy(self, instance):
        deleted = {'vendor': instance.vendor, 'amount': str(instance.amount),
                   'category': instance.category.name if instance.category else None,
                   'date': str(instance.date)}
        AuditLog.objects.create(
            tenant=_require_tenant(self.request.user), user=self.request.user,
            action='delete', model_type='expense', object_id=instance.id,
            object_repr=f"Expense: {instance.vendor}", changes={'deleted': deleted},
            ip_address=self._get_ip(), user_agent=self.request.META.get('HTTP_USER_AGENT', '')[:500],
            endpoint=self.request.path, method=self.request.method, is_suspicious=True,
        )
        instance.delete()

    def _get_ip(self):
        xff = self.request.META.get('HTTP_X_FORWARDED_FOR')
        return xff.split(',')[0] if xff else self.request.META.get('REMOTE_ADDR')

    @action(detail=False, methods=['get'])
    def summary(self, request):
        expenses = self.get_queryset()
        total = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        this_month = expenses.filter(date__gte=month_start).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        twelve_months_ago = now.date() - timedelta(days=365)
        last_year_total = expenses.filter(date__gte=twelve_months_ago).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        avg_per_month = last_year_total / 12 if last_year_total else Decimal('0')
        by_category = expenses.values('category__name', 'category_id').annotate(total=Sum('amount'), count=Count('id')).order_by('-total')
        highest_category = None
        if by_category.exists():
            h = by_category[0]
            pct = (float(h['total']) / float(total) * 100) if total > 0 else 0
            highest_category = {'name': h['category__name'] or 'Uncategorized', 'total': float(h['total']), 'percentage': round(pct, 1), 'count': h['count']}
        by_payment_method = expenses.values('payment_method').annotate(total=Sum('amount'))
        trend = []
        prev_total = None
        for i in range(12):
            ms = twelve_months_ago + timedelta(days=30 * i)
            me = ms + timedelta(days=30)
            mt = expenses.filter(date__gte=ms, date__lt=me).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            change = ((float(mt) - float(prev_total)) / float(prev_total) * 100) if prev_total and prev_total > 0 else 0
            trend.append({'month': ms.strftime('%b %Y'), 'total': float(mt), 'change_percent': round(change, 1) if prev_total else None})
            prev_total = mt
        if len(trend) >= 3:
            changes = [t['change_percent'] for t in trend[-3:] if t['change_percent'] is not None]
            avg_change = sum(changes) / len(changes) if changes else 0
            trend_direction = 'rising' if avg_change > 5 else 'falling' if avg_change < -5 else 'stable'
        else:
            trend_direction = 'unknown'
        top_vendors = expenses.values('vendor').annotate(total=Sum('amount'), count=Count('id')).order_by('-total')[:5]
        return Response({
            'total_expenses': float(total), 'this_month': float(this_month),
            'avg_per_month': float(avg_per_month), 'highest_category': highest_category,
            'trend_direction': trend_direction, 'by_category': list(by_category),
            'by_payment_method': list(by_payment_method), 'top_vendors': list(top_vendors),
            'trend': trend, 'expense_count': expenses.count(),
        })


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = _get_tenant(self.request.user)
        if not tenant:
            return Payment.objects.none()
        qs = Payment.objects.filter(tenant=tenant)
        p = self.request.query_params
        if p.get('type'):
            qs = qs.filter(payment_type=p['type'])
        if p.get('status'):
            qs = qs.filter(status=p['status'])
        if p.get('date_from'):
            qs = qs.filter(date__gte=p['date_from'])
        if p.get('date_to'):
            qs = qs.filter(date__lte=p['date_to'])
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=_require_tenant(self.request.user), created_by=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        old = {'party_name': instance.party_name, 'amount': str(instance.amount),
               'payment_type': instance.payment_type, 'status': instance.status,
               'payment_method': instance.payment_method, 'date': str(instance.date)}
        updated = serializer.save(updated_by=self.request.user)
        new = {'party_name': updated.party_name, 'amount': str(updated.amount),
               'payment_type': updated.payment_type, 'status': updated.status,
               'payment_method': updated.payment_method, 'date': str(updated.date)}
        AuditLog.objects.create(
            tenant=_require_tenant(self.request.user), user=self.request.user,
            action='update', model_type='payment', object_id=updated.id,
            object_repr=f"Payment: {updated.party_name}", changes={'before': old, 'after': new},
            ip_address=self._get_ip(), user_agent=self.request.META.get('HTTP_USER_AGENT', '')[:500],
            endpoint=self.request.path, method=self.request.method,
        )

    def perform_destroy(self, instance):
        deleted = {'party_name': instance.party_name, 'amount': str(instance.amount),
                   'payment_type': instance.payment_type, 'status': instance.status, 'date': str(instance.date)}
        AuditLog.objects.create(
            tenant=_require_tenant(self.request.user), user=self.request.user,
            action='delete', model_type='payment', object_id=instance.id,
            object_repr=f"Payment: {instance.party_name}", changes={'deleted': deleted},
            ip_address=self._get_ip(), user_agent=self.request.META.get('HTTP_USER_AGENT', '')[:500],
            endpoint=self.request.path, method=self.request.method, is_suspicious=True,
        )
        instance.delete()

    def _get_ip(self):
        xff = self.request.META.get('HTTP_X_FORWARDED_FOR')
        return xff.split(',')[0] if xff else self.request.META.get('REMOTE_ADDR')

    @action(detail=False, methods=['get'])
    def summary(self, request):
        payments = self.get_queryset()
        now = timezone.now()
        income_total = payments.filter(payment_type='income', status='paid').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        income_pending = payments.filter(payment_type='income', status='pending').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        income_count = payments.filter(payment_type='income').count()
        expense_total = payments.filter(payment_type='expense', status='paid').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        expense_pending = payments.filter(payment_type='expense', status='pending').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        expense_count = payments.filter(payment_type='expense').count()
        net = income_total - expense_total
        projected_net = (income_total + income_pending) - (expense_total + expense_pending)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        this_month_income = payments.filter(payment_type='income', status='paid', date__gte=month_start).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        this_month_expense = payments.filter(payment_type='expense', status='paid', date__gte=month_start).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        overdue_income = payments.filter(payment_type='income', status='pending', due_date__lt=now.date()).count()
        overdue_expense = payments.filter(payment_type='expense', status='pending', due_date__lt=now.date()).count()
        by_payment_method = payments.filter(status='paid').values('payment_method').annotate(total=Sum('amount'), count=Count('id')).order_by('-total')
        by_status = payments.values('status').annotate(count=Count('id'), total=Sum('amount'))
        twelve_months_ago = now.date() - timedelta(days=365)
        trend = []
        prev_income = prev_expense = None
        for i in range(12):
            ms = twelve_months_ago + timedelta(days=30 * i)
            me = ms + timedelta(days=30)
            mi = payments.filter(payment_type='income', status='paid', date__gte=ms, date__lt=me).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            me2 = payments.filter(payment_type='expense', status='paid', date__gte=ms, date__lt=me).aggregate(total=Sum('amount'))['total'] or Decimal('0')
            ic = ((float(mi) - float(prev_income)) / float(prev_income) * 100) if prev_income and prev_income > 0 else 0
            ec = ((float(me2) - float(prev_expense)) / float(prev_expense) * 100) if prev_expense and prev_expense > 0 else 0
            trend.append({'month': ms.strftime('%b %Y'), 'income': float(mi), 'expense': float(me2), 'net': float(mi - me2),
                          'income_change': round(ic, 1) if prev_income else None, 'expense_change': round(ec, 1) if prev_expense else None})
            prev_income, prev_expense = mi, me2
        if len(trend) >= 3:
            avg_net = sum(t['net'] for t in trend[-3:]) / 3
            trend_direction = 'positive' if avg_net > 0 else 'negative' if avg_net < 0 else 'neutral'
        else:
            trend_direction = 'unknown'
        avg_income = income_total / income_count if income_count > 0 else Decimal('0')
        avg_expense = expense_total / expense_count if expense_count > 0 else Decimal('0')
        top_income_parties = payments.filter(payment_type='income', status='paid').values('party_name').annotate(total=Sum('amount'), count=Count('id')).order_by('-total')[:5]
        top_expense_parties = payments.filter(payment_type='expense', status='paid').values('party_name').annotate(total=Sum('amount'), count=Count('id')).order_by('-total')[:5]
        return Response({
            'total_income': float(income_total), 'total_expenses': float(expense_total),
            'net': float(net), 'projected_net': float(projected_net),
            'this_month_income': float(this_month_income), 'this_month_expense': float(this_month_expense),
            'this_month_net': float(this_month_income - this_month_expense),
            'pending_income': float(income_pending), 'pending_expenses': float(expense_pending),
            'overdue_income_count': overdue_income, 'overdue_expense_count': overdue_expense,
            'total_overdue_count': overdue_income + overdue_expense,
            'avg_income': float(avg_income), 'avg_expense': float(avg_expense),
            'income_count': income_count, 'expense_count': expense_count, 'total_count': payments.count(),
            'by_payment_method': list(by_payment_method), 'by_status': list(by_status),
            'top_income_parties': list(top_income_parties), 'top_expense_parties': list(top_expense_parties),
            'trend': trend, 'trend_direction': trend_direction,
        })


class TaxViewSet(viewsets.ModelViewSet):
    serializer_class = TaxSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = _get_tenant(self.request.user)
        if not tenant:
            return Tax.objects.none()
        qs = Tax.objects.filter(tenant=tenant)
        p = self.request.query_params
        if p.get('type'):
            qs = qs.filter(tax_type=p['type'])
        if p.get('status'):
            qs = qs.filter(status=p['status'])
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=_require_tenant(self.request.user), created_by=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        old = {'tax_type': instance.tax_type, 'amount': str(instance.amount),
               'status': instance.status, 'due_date': str(instance.due_date),
               'period': f"{instance.period_start} to {instance.period_end}"}
        updated = serializer.save(updated_by=self.request.user)
        new = {'tax_type': updated.tax_type, 'amount': str(updated.amount),
               'status': updated.status, 'due_date': str(updated.due_date),
               'period': f"{updated.period_start} to {updated.period_end}"}
        AuditLog.objects.create(
            tenant=_require_tenant(self.request.user), user=self.request.user,
            action='update', model_type='tax', object_id=updated.id,
            object_repr=f"Tax: {updated.get_tax_type_display()}", changes={'before': old, 'after': new},
            ip_address=self._get_ip(), user_agent=self.request.META.get('HTTP_USER_AGENT', '')[:500],
            endpoint=self.request.path, method=self.request.method,
        )

    def perform_destroy(self, instance):
        deleted = {'tax_type': instance.tax_type, 'amount': str(instance.amount),
                   'status': instance.status, 'due_date': str(instance.due_date)}
        AuditLog.objects.create(
            tenant=_require_tenant(self.request.user), user=self.request.user,
            action='delete', model_type='tax', object_id=instance.id,
            object_repr=f"Tax: {instance.get_tax_type_display()}", changes={'deleted': deleted},
            ip_address=self._get_ip(), user_agent=self.request.META.get('HTTP_USER_AGENT', '')[:500],
            endpoint=self.request.path, method=self.request.method, is_suspicious=True,
        )
        instance.delete()

    def _get_ip(self):
        xff = self.request.META.get('HTTP_X_FORWARDED_FOR')
        return xff.split(',')[0] if xff else self.request.META.get('REMOTE_ADDR')

    @action(detail=False, methods=['get'])
    def summary(self, request):
        taxes = self.get_queryset()
        total_due = taxes.filter(status='due').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        total_paid = taxes.filter(status='paid').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        overdue_count = taxes.filter(status='overdue').count()
        upcoming = taxes.filter(due_date__gte=timezone.now().date(),
                                due_date__lte=timezone.now().date() + timedelta(days=30), status='due')
        by_type = taxes.values('tax_type').annotate(total=Sum('amount'))
        return Response({
            'total_due': float(total_due), 'total_paid': float(total_paid),
            'overdue_count': overdue_count,
            'upcoming_taxes': TaxSerializer(upcoming, many=True).data,
            'by_type': list(by_type),
        })


class AssetViewSet(viewsets.ModelViewSet):
    serializer_class = AssetSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = _get_tenant(self.request.user)
        if not tenant:
            return Asset.objects.none()
        return Asset.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=_require_tenant(self.request.user))


class LiabilityViewSet(viewsets.ModelViewSet):
    serializer_class = LiabilitySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = _get_tenant(self.request.user)
        if not tenant:
            return Liability.objects.none()
        return Liability.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=_require_tenant(self.request.user))


class EquityViewSet(viewsets.ModelViewSet):
    serializer_class = EquitySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = _get_tenant(self.request.user)
        if not tenant:
            return Equity.objects.none()
        return Equity.objects.filter(tenant=tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=_require_tenant(self.request.user))


class ProfitLossViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        tenant = _get_tenant(request.user)
        if not tenant:
            from core.auth_views import ensure_tenant_for_user
            tenant = ensure_tenant_for_user(request.user)
        if not tenant:
            return Response({'error': 'No tenant found.'}, status=status.HTTP_403_FORBIDDEN)
        if not getattr(tenant, 'is_verified', False):
            tenant.is_verified = True
            tenant.save(update_fields=['is_verified'])

        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if not date_from or not date_to:
            date_to = timezone.now().date()
            date_from = date_to.replace(month=1, day=1)

        revenue = Order.objects.filter(
            tenant=tenant, date__gte=date_from, date__lte=date_to,
            status__in=['confirmed', 'delivered']
        ).aggregate(total=Sum('total'))['total'] or Decimal('0')

        expenses = Expense.objects.filter(
            tenant=tenant, date__gte=date_from, date__lte=date_to
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        expense_by_category = Expense.objects.filter(
            tenant=tenant, date__gte=date_from, date__lte=date_to
        ).values('category__name').annotate(total=Sum('amount')).order_by('-total')

        net_profit = revenue - expenses
        profit_margin = (net_profit / revenue * 100) if revenue > 0 else 0

        return Response({
            'period': {'start': date_from, 'end': date_to},
            'revenue': float(revenue), 'expenses': float(expenses),
            'expense_breakdown': list(expense_by_category),
            'net_profit': float(net_profit), 'profit_margin': float(profit_margin),
        })


class BalanceSheetViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        tenant = _get_tenant(request.user)
        if not tenant:
            return Response({'error': 'No tenant found.'}, status=status.HTTP_403_FORBIDDEN)

        def asset_sum(asset_type):
            return Asset.objects.filter(tenant=tenant, asset_type=asset_type).aggregate(total=Sum('value'))['total'] or Decimal('0')

        def liability_sum(liability_type):
            return Liability.objects.filter(tenant=tenant, liability_type=liability_type).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        def equity_sum(equity_type):
            return Equity.objects.filter(tenant=tenant, equity_type=equity_type).aggregate(total=Sum('amount'))['total'] or Decimal('0')

        current_assets = asset_sum('current')
        fixed_assets = asset_sum('fixed')
        intangible_assets = asset_sum('intangible')
        total_assets = current_assets + fixed_assets + intangible_assets

        current_liabilities = liability_sum('current')
        long_term_liabilities = liability_sum('long_term')
        total_liabilities = current_liabilities + long_term_liabilities

        owner_capital = equity_sum('capital')
        retained_earnings = equity_sum('retained_earnings')
        owner_draws = equity_sum('draws')
        total_equity = owner_capital + retained_earnings - owner_draws

        balance_check = total_assets - (total_liabilities + total_equity)

        return Response({
            'assets': {'current_assets': float(current_assets), 'fixed_assets': float(fixed_assets),
                       'intangible_assets': float(intangible_assets), 'total': float(total_assets)},
            'liabilities': {'current_liabilities': float(current_liabilities),
                            'long_term_liabilities': float(long_term_liabilities), 'total': float(total_liabilities)},
            'equity': {'owner_capital': float(owner_capital), 'retained_earnings': float(retained_earnings),
                       'owner_draws': float(owner_draws), 'total': float(total_equity)},
            'total_liabilities_and_equity': float(total_liabilities + total_equity),
            'balance_check': float(balance_check),
            'is_balanced': abs(balance_check) < Decimal('0.01'),
        })


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = _get_tenant(self.request.user)
        if not tenant:
            return AuditLog.objects.none()
        qs = AuditLog.objects.filter(tenant=tenant)
        p = self.request.query_params
        if p.get('user'):
            qs = qs.filter(user_id=p['user'])
        if p.get('action'):
            qs = qs.filter(action=p['action'])
        if p.get('model_type'):
            qs = qs.filter(model_type=p['model_type'])
        if p.get('object_id'):
            qs = qs.filter(object_id=p['object_id'])
        if p.get('is_suspicious') == 'true':
            qs = qs.filter(is_suspicious=True)
        if p.get('date_from'):
            qs = qs.filter(timestamp__gte=p['date_from'])
        if p.get('date_to'):
            qs = qs.filter(timestamp__lte=p['date_to'])
        return qs.select_related('user')

    @action(detail=False, methods=['get'])
    def summary(self, request):
        logs = self.get_queryset()
        by_action = {code: {'name': name, 'count': logs.filter(action=code).count()} for code, name in AuditLog.ACTION_TYPES}
        by_model = {code: {'name': name, 'count': logs.filter(model_type=code).count()} for code, name in AuditLog.MODEL_TYPES}
        suspicious_logs = AuditLogSerializer(logs.filter(is_suspicious=True).order_by('-timestamp')[:10], many=True).data
        active_users = logs.values('user__username', 'user__email').annotate(action_count=Count('id')).order_by('-action_count')[:10]
        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        recent = logs.filter(timestamp__gte=twenty_four_hours_ago)
        hourly = []
        for i in range(24):
            hs = twenty_four_hours_ago + timedelta(hours=i)
            hourly.append({'hour': hs.strftime('%H:00'), 'count': recent.filter(timestamp__gte=hs, timestamp__lt=hs + timedelta(hours=1)).count()})
        return Response({
            'total_logs': logs.count(), 'by_action': by_action, 'by_model': by_model,
            'suspicious_count': logs.filter(is_suspicious=True).count(),
            'suspicious_logs': suspicious_logs, 'active_users': list(active_users),
            'hourly_activity': hourly,
            'date_range': {
                'oldest': logs.order_by('timestamp').first().timestamp if logs.exists() else None,
                'newest': logs.order_by('-timestamp').first().timestamp if logs.exists() else None,
            },
        })
