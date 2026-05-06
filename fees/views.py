from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum
from students.models import Student
from .models import FeeStructure, FeePayment, ReceiptSettings
from .serializers import FeeStructureSerializer, FeePaymentSerializer, ReceiptSettingsSerializer
from core.tenant_utils import get_tenant_for_user


class FeeStructureViewSet(viewsets.ModelViewSet):
    serializer_class = FeeStructureSerializer
    permission_classes = [IsAuthenticated]

    def get_tenant(self):
        return get_tenant_for_user(self.request.user)

    def get_queryset(self):
        tenant = self.get_tenant()
        qs = FeeStructure.objects.filter(tenant=tenant) if tenant else FeeStructure.objects.none()
        for f in ('term', 'academic_year', 'class_assigned'):
            v = self.request.query_params.get(f)
            if v:
                qs = qs.filter(**{f: v})
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=self.get_tenant())

    @action(detail=False, methods=['post'], url_path='bulk_upsert')
    def bulk_upsert(self, request):
        tenant = self.get_tenant()
        rows = request.data
        if not isinstance(rows, list):
            return Response({'error': 'Expected a list.'}, status=400)
        saved = []
        for row in rows:
            if not row.get('amount') and row.get('amount') != 0:
                continue
            obj, _ = FeeStructure.objects.update_or_create(
                tenant=tenant,
                class_assigned=row['class_assigned'],
                term=row['term'],
                academic_year=row['academic_year'],
                defaults={'amount': row['amount'], 'description': row.get('description', '')},
            )
            saved.append(FeeStructureSerializer(obj).data)
        return Response(saved, status=200)


class FeePaymentViewSet(viewsets.ModelViewSet):
    serializer_class = FeePaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_tenant(self):
        return get_tenant_for_user(self.request.user)

    def get_queryset(self):
        tenant = self.get_tenant()
        qs = FeePayment.objects.select_related('student').filter(tenant=tenant) if tenant else FeePayment.objects.none()
        for f in ('term', 'academic_year'):
            v = self.request.query_params.get(f)
            if v:
                qs = qs.filter(**{f: v})
        student_id = self.request.query_params.get('student')
        if student_id:
            qs = qs.filter(student_id=student_id)
        cls = self.request.query_params.get('class_assigned')
        if cls:
            qs = qs.filter(student__class_assigned=cls)
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=self.get_tenant())

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        tenant = get_tenant_for_user(request.user)
        term = request.query_params.get('term', '')
        academic_year = request.query_params.get('academic_year', '')
        class_filter = request.query_params.get('class_assigned', '')

        students_qs = Student.objects.filter(tenant=tenant) if tenant else Student.objects.none()
        if class_filter:
            students_qs = students_qs.filter(class_assigned=class_filter)

        structure_qs = FeeStructure.objects.filter(tenant=tenant) if tenant else FeeStructure.objects.none()
        if term:
            structure_qs = structure_qs.filter(term=term)
        if academic_year:
            structure_qs = structure_qs.filter(academic_year=academic_year)
        structure_map = {s.class_assigned: float(s.amount) for s in structure_qs}

        payments_qs = FeePayment.objects.filter(tenant=tenant) if tenant else FeePayment.objects.none()
        if term:
            payments_qs = payments_qs.filter(term=term)
        if academic_year:
            payments_qs = payments_qs.filter(academic_year=academic_year)
        if class_filter:
            payments_qs = payments_qs.filter(student__class_assigned=class_filter)

        paid_map = {}
        for row in payments_qs.values('student_id').annotate(total=Sum('amount_paid')):
            paid_map[row['student_id']] = float(row['total'])

        rows = []
        for s in students_qs:
            required = structure_map.get(s.class_assigned, 0)
            paid = paid_map.get(s.id, 0)
            balance = required - paid
            if required == 0:
                pay_status = 'no_structure'
            elif paid >= required:
                pay_status = 'paid'
            elif paid > 0:
                pay_status = 'partial'
            else:
                pay_status = 'not_paid'
            rows.append({
                'student_id': s.id,
                'student_name': f"{s.first_name} {s.last_name}",
                'admission_number': s.admission_number or '—',
                'class_assigned': s.class_assigned,
                'required': required,
                'paid': paid,
                'balance': balance,
                'payment_status': pay_status,
            })

        return Response({
            'students': rows,
            'totals': {
                'required': sum(r['required'] for r in rows),
                'paid': sum(r['paid'] for r in rows),
                'balance': sum(r['balance'] for r in rows),
                'count_paid': sum(1 for r in rows if r['payment_status'] == 'paid'),
                'count_partial': sum(1 for r in rows if r['payment_status'] == 'partial'),
                'count_not_paid': sum(1 for r in rows if r['payment_status'] == 'not_paid'),
            }
        })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def receipt_settings_view(request):
    from tenants.models import TenantMembership, Tenant
    # Scope receipt settings to the tenant admin so all workers share the same stamp/sig
    user = request.user
    try:
        tenant = user.tenant_admin
        owner = tenant.admin
    except Tenant.DoesNotExist:
        membership = TenantMembership.objects.filter(user=user).select_related('tenant__admin').first()
        owner = membership.tenant.admin if membership else user

    obj, _ = ReceiptSettings.objects.get_or_create(user=owner)
    if request.method == 'GET':
        return Response(ReceiptSettingsSerializer(obj).data)
    serializer = ReceiptSettingsSerializer(obj, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)
