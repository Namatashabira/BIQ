from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum
from students.models import Student
from .models import FeeStructure, FeeItem, FeePayment, FeeItemPayment, ReceiptSettings
from .serializers import FeeStructureSerializer, FeeItemSerializer, FeePaymentSerializer, FeeItemPaymentSerializer, ReceiptSettingsSerializer
from core.tenant_utils import get_tenant_for_user


class FeeStructureViewSet(viewsets.ModelViewSet):
    serializer_class = FeeStructureSerializer
    permission_classes = [IsAuthenticated]

    def get_tenant(self):
        return get_tenant_for_user(self.request.user)

    def get_queryset(self):
        tenant = self.get_tenant()
        qs = FeeStructure.objects.prefetch_related('items').filter(tenant=tenant) if tenant else FeeStructure.objects.none()
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


class FeeItemViewSet(viewsets.ModelViewSet):
    """CRUD for fee line items within a structure (Uniform, Books, etc.)."""
    serializer_class = FeeItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = get_tenant_for_user(self.request.user)
        qs = FeeItem.objects.select_related('structure').filter(structure__tenant=tenant)
        structure_id = self.request.query_params.get('structure')
        if structure_id:
            qs = qs.filter(structure_id=structure_id)
        return qs


class FeeItemPaymentViewSet(viewsets.ModelViewSet):
    """Tracks which FeeItems a student has paid."""
    serializer_class = FeeItemPaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_tenant(self):
        return get_tenant_for_user(self.request.user)

    def get_queryset(self):
        tenant = self.get_tenant()
        qs = FeeItemPayment.objects.select_related('item', 'student').filter(tenant=tenant)
        student_id = self.request.query_params.get('student')
        if student_id:
            qs = qs.filter(student_id=student_id)
        structure_id = self.request.query_params.get('structure')
        if structure_id:
            qs = qs.filter(item__structure_id=structure_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=self.get_tenant())

    @action(detail=False, methods=['post'], url_path='bulk-mark')
    def bulk_mark(self, request):
        """Mark multiple items as paid for a student in one call."""
        tenant = self.get_tenant()
        student_id = request.data.get('student')
        item_ids = request.data.get('item_ids', [])
        payment_id = request.data.get('payment_id')
        if not student_id or not item_ids:
            return Response({'error': 'student and item_ids required'}, status=400)
        created = []
        for item_id in item_ids:
            obj, _ = FeeItemPayment.objects.get_or_create(
                student_id=student_id, item_id=item_id,
                defaults={'tenant': tenant, 'payment_id': payment_id}
            )
            created.append(obj.id)
        return Response({'marked': len(created)})

    @action(detail=False, methods=['post'], url_path='bulk-unmark')
    def bulk_unmark(self, request):
        """Unmark (remove) item payments for a student."""
        student_id = request.data.get('student')
        item_ids = request.data.get('item_ids', [])
        if not student_id:
            return Response({'error': 'student required'}, status=400)
        deleted, _ = FeeItemPayment.objects.filter(student_id=student_id, item_id__in=item_ids).delete()
        return Response({'deleted': deleted})


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
        payment_category = self.request.query_params.get('payment_category')
        if payment_category:
            qs = qs.filter(payment_category=payment_category)
        cls = self.request.query_params.get('class_assigned')
        if cls:
            qs = qs.filter(student__class_assigned=cls)
        return qs

    def _validate_school_fees_cap(self, student_id, term, academic_year, amount_paid, exclude_payment_id=None):
        """Returns error string if school_fees payment would exceed the structure amount."""
        try:
            student = Student.objects.get(pk=student_id)
        except Student.DoesNotExist:
            return None
        tenant = self.get_tenant()
        try:
            structure = FeeStructure.objects.get(tenant=tenant, class_assigned=student.class_assigned, term=term, academic_year=academic_year)
        except FeeStructure.DoesNotExist:
            return None  # no structure set — allow payment
        existing_qs = FeePayment.objects.filter(
            tenant=tenant, student_id=student_id, term=term,
            academic_year=academic_year, payment_category='school_fees'
        )
        if exclude_payment_id:
            existing_qs = existing_qs.exclude(pk=exclude_payment_id)
        already_paid = float(existing_qs.aggregate(t=Sum('amount_paid'))['t'] or 0)
        if already_paid + float(amount_paid) > float(structure.amount):
            remaining = float(structure.amount) - already_paid
            return f"School fees cap exceeded. Structure: UGX {structure.amount:,.0f}. Already paid: UGX {already_paid:,.0f}. Max you can add: UGX {max(remaining, 0):,.0f}."
        return None

    def create(self, request, *args, **kwargs):
        data = request.data
        if data.get('payment_category') == 'school_fees':
            err = self._validate_school_fees_cap(
                data.get('student'), data.get('term'), data.get('academic_year'), data.get('amount_paid', 0)
            )
            if err:
                return Response({'detail': err, 'code': 'cap_exceeded'}, status=status.HTTP_400_BAD_REQUEST)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        data = request.data
        if data.get('payment_category') == 'school_fees':
            err = self._validate_school_fees_cap(
                data.get('student'), data.get('term'), data.get('academic_year'),
                data.get('amount_paid', 0), exclude_payment_id=kwargs.get('pk')
            )
            if err:
                return Response({'detail': err, 'code': 'cap_exceeded'}, status=status.HTTP_400_BAD_REQUEST)
        return super().update(request, *args, **kwargs)

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

        structure_qs = FeeStructure.objects.prefetch_related('items').filter(tenant=tenant) if tenant else FeeStructure.objects.none()
        if term:
            structure_qs = structure_qs.filter(term=term)
        if academic_year:
            structure_qs = structure_qs.filter(academic_year=academic_year)

        # Map class -> structure (amount + items)
        structure_map = {}  # class_assigned -> {amount, items: [{id, name, amount, is_optional}]}
        for s in structure_qs:
            structure_map[s.class_assigned] = {
                'structure_id': s.id,
                'amount': float(s.amount),
                'items': [{'id': it.id, 'name': it.name, 'amount': float(it.amount), 'is_optional': it.is_optional} for it in s.items.all()],
            }

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

        # Item payments: which items each student has paid
        item_paid_qs = FeeItemPayment.objects.filter(tenant=tenant).select_related('item')
        if class_filter:
            item_paid_qs = item_paid_qs.filter(student__class_assigned=class_filter)
        item_paid_map = {}  # student_id -> set of item_ids
        for ip in item_paid_qs:
            item_paid_map.setdefault(ip.student_id, set()).add(ip.item_id)

        rows = []
        for s in students_qs:
            struct = structure_map.get(s.class_assigned, {})
            required = struct.get('amount', 0)
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

            # Build unpaid items list
            all_items = struct.get('items', [])
            paid_item_ids = item_paid_map.get(s.id, set())
            unpaid_items = [it for it in all_items if it['id'] not in paid_item_ids]

            rows.append({
                'student_id': s.id,
                'student_name': f"{s.first_name} {s.last_name}",
                'admission_number': s.admission_number or '—',
                'class_assigned': s.class_assigned,
                'photo': s.photo.url if s.photo else None,
                'required': required,
                'paid': paid,
                'balance': balance,
                'payment_status': pay_status,
                'structure_id': struct.get('structure_id'),
                'all_items': all_items,
                'unpaid_items': unpaid_items,
                'paid_item_ids': list(paid_item_ids),
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


@api_view(['GET'])
@permission_classes([])
def public_receipt_lookup(request, receipt_number):
    """Public endpoint — no auth required. Returns payment + student info for a receipt number."""
    from django.db.models import Sum
    try:
        payment = FeePayment.objects.select_related('student', 'tenant').get(receipt_number=receipt_number)
    except FeePayment.DoesNotExist:
        return Response({'detail': 'Receipt not found.'}, status=404)

    student = payment.student
    # All payments for same student/term/year so we can show balance
    all_payments = FeePayment.objects.filter(
        tenant=payment.tenant, student=student,
        term=payment.term, academic_year=payment.academic_year
    ).order_by('payment_date')
    total_paid = float(all_payments.aggregate(t=Sum('amount_paid'))['t'] or 0)

    # Try to get fee structure for balance
    balance = None
    try:
        from .models import FeeStructure
        structure = FeeStructure.objects.get(
            tenant=payment.tenant,
            class_assigned=student.class_assigned,
            term=payment.term,
            academic_year=payment.academic_year,
        )
        balance = float(structure.amount) - total_paid
    except Exception:
        pass

    return Response({
        'receipt_number': payment.receipt_number,
        'payment': FeePaymentSerializer(payment).data,
        'student': {
            'id': student.id,
            'first_name': student.first_name,
            'last_name': student.last_name,
            'admission_number': student.admission_number or '—',
            'class_assigned': student.class_assigned,
            'index_number': getattr(student, 'index_number', ''),
            'stream_name': getattr(student, 'stream_name', ''),
            'gender': getattr(student, 'gender', ''),
        },
        'all_payments': FeePaymentSerializer(all_payments, many=True).data,
        'total_paid': total_paid,
        'balance': balance,
        'school_name': payment.tenant.name if payment.tenant else '',
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
