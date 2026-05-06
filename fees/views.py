from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum
from students.models import Student
from .models import FeeStructure, FeePayment, ReceiptSettings
from .serializers import FeeStructureSerializer, FeePaymentSerializer, ReceiptSettingsSerializer


class FeeStructureViewSet(viewsets.ModelViewSet):
    queryset = FeeStructure.objects.all()
    serializer_class = FeeStructureSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        for f in ('term', 'academic_year', 'class_assigned'):
            v = self.request.query_params.get(f)
            if v:
                qs = qs.filter(**{f: v})
        return qs

    @action(detail=False, methods=['post'], url_path='bulk_upsert')
    def bulk_upsert(self, request):
        """
        Accepts a list of {class_assigned, term, academic_year, amount, description}.
        Creates or updates each row (unique_together: class_assigned+term+academic_year).
        """
        rows = request.data
        if not isinstance(rows, list):
            return Response({'error': 'Expected a list.'}, status=400)
        saved = []
        for row in rows:
            if not row.get('amount') and row.get('amount') != 0:
                continue
            obj, _ = FeeStructure.objects.update_or_create(
                class_assigned=row['class_assigned'],
                term=row['term'],
                academic_year=row['academic_year'],
                defaults={'amount': row['amount'], 'description': row.get('description', '')},
            )
            saved.append(FeeStructureSerializer(obj).data)
        return Response(saved, status=200)


class FeePaymentViewSet(viewsets.ModelViewSet):
    queryset = FeePayment.objects.select_related('student').all()
    serializer_class = FeePaymentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
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

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """
        Returns per-student fee summary for a given term + academic_year.
        Query params: term, academic_year, class_assigned (optional)
        """
        term = request.query_params.get('term', '')
        academic_year = request.query_params.get('academic_year', '')
        class_filter = request.query_params.get('class_assigned', '')

        students_qs = Student.objects.all()
        if class_filter:
            students_qs = students_qs.filter(class_assigned=class_filter)

        # Build structure lookup: class -> required amount
        structure_qs = FeeStructure.objects.all()
        if term:
            structure_qs = structure_qs.filter(term=term)
        if academic_year:
            structure_qs = structure_qs.filter(academic_year=academic_year)
        structure_map = {s.class_assigned: float(s.amount) for s in structure_qs}

        # Build payments lookup: student_id -> total paid
        payments_qs = FeePayment.objects.all()
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

        # Aggregate totals
        total_required = sum(r['required'] for r in rows)
        total_paid = sum(r['paid'] for r in rows)
        total_balance = sum(r['balance'] for r in rows)

        return Response({
            'students': rows,
            'totals': {
                'required': total_required,
                'paid': total_paid,
                'balance': total_balance,
                'count_paid': sum(1 for r in rows if r['payment_status'] == 'paid'),
                'count_partial': sum(1 for r in rows if r['payment_status'] == 'partial'),
                'count_not_paid': sum(1 for r in rows if r['payment_status'] == 'not_paid'),
            }
        })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def receipt_settings_view(request):
    obj, _ = ReceiptSettings.objects.get_or_create(user=request.user)
    if request.method == 'GET':
        return Response(ReceiptSettingsSerializer(obj).data)
    serializer = ReceiptSettingsSerializer(obj, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)
