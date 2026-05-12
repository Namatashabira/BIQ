from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Student, Stream, Guardian, StudentHistory, StudentMark, GeneratedReport, Attendance, CLASS_CHOICES, SCHOOL_TYPE_CHOICES
from .serializers import (
    StudentSerializer, StreamSerializer,
    GuardianSerializer, StudentHistorySerializer, StudentMarkSerializer,
    GeneratedReportSerializer, AttendanceSerializer,
)
from core.tenant_utils import get_tenant_for_user


class TenantScopedMixin:
    """Mixin that scopes all querysets to the current user's tenant."""
    permission_classes = [IsAuthenticated]

    def get_tenant(self):
        return get_tenant_for_user(self.request.user)

    def perform_create(self, serializer):
        serializer.save(tenant=self.get_tenant())


class StudentViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    serializer_class = StudentSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        tenant = self.get_tenant()
        qs = Student.objects.select_related('stream').prefetch_related('guardians', 'history')
        if tenant:
            qs = qs.filter(tenant=tenant)
        else:
            qs = qs.none()
        search = self.request.query_params.get('search', '')
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(admission_number__icontains=search) |
                Q(index_number__icontains=search)
            )
        cls = self.request.query_params.get('class_assigned')
        if cls:
            qs = qs.filter(class_assigned=cls)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def _inject_photo(self, request):
        data = request.data.copy()
        if 'photo' in request.FILES:
            data['photo_upload'] = request.FILES['photo']
        return data

    def create(self, request, *args, **kwargs):
        data = self._inject_photo(request)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(tenant=self.get_tenant())
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        data = self._inject_photo(request)
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='meta')
    def meta(self, request):
        tenant = self.get_tenant()
        streams_qs = Stream.objects.filter(tenant=tenant) if tenant else Stream.objects.none()
        primary_classes = [v for v, _ in CLASS_CHOICES if v in ('Baby','Middle','Top') or v.startswith('P.')]
        secondary_classes = [v for v, _ in CLASS_CHOICES if v.startswith('S.')]
        return Response({
            'classes': [{'value': v, 'label': l} for v, l in CLASS_CHOICES],
            'primary_classes': primary_classes,
            'secondary_classes': secondary_classes,
            'school_types': [{'value': v, 'label': l} for v, l in SCHOOL_TYPE_CHOICES],
            'streams': StreamSerializer(streams_qs, many=True).data,
        })

    @action(detail=True, methods=['get', 'post'], url_path='guardians')
    def guardians(self, request, pk=None):
        student = self.get_object()
        if request.method == 'POST':
            serializer = GuardianSerializer(data={**request.data, 'student': student.id})
            serializer.is_valid(raise_exception=True)
            serializer.save(student=student)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(GuardianSerializer(student.guardians.all(), many=True).data)

    @action(detail=True, methods=['get', 'post'], url_path='history')
    def history(self, request, pk=None):
        student = self.get_object()
        if request.method == 'POST':
            serializer = StudentHistorySerializer(data={**request.data, 'student': student.id})
            serializer.is_valid(raise_exception=True)
            serializer.save(student=student)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(StudentHistorySerializer(student.history.all(), many=True).data)

    @action(detail=True, methods=['get'], url_path='report')
    def report(self, request, pk=None):
        student = self.get_object()
        term = request.query_params.get('term', '')
        academic_year = request.query_params.get('academic_year', '')

        qs = student.history.filter(history_type='performance')
        if term:
            qs = qs.filter(title__icontains=term)
        if academic_year:
            qs = qs.filter(date__year=academic_year)

        subjects = [{
            'subject_name': r.title,
            'subject_code': r.title[:6].upper(),
            'score': 0, 'grade': '—',
            'remark': r.description or '',
            'date': str(r.date),
            'competencies': [],
        } for r in qs.order_by('-date')]

        attendance = list(student.history.filter(history_type='attendance').order_by('-date').values('title', 'description', 'date'))
        notes = list(student.history.filter(history_type='note').order_by('-date').values('title', 'description', 'date'))
        guardians = [{'full_name': g.full_name, 'relationship': g.relationship, 'phone': g.phone, 'email': g.email or ''} for g in student.guardians.all()]

        return Response({
            'student': {
                'id': student.id,
                'full_name': f'{student.first_name} {student.last_name}',
                'admission_number': student.admission_number or '—',
                'class_or_grade': student.class_assigned or '—',
                'stream': student.stream.name if student.stream else '—',
                'date_of_birth': str(student.date_of_birth) if student.date_of_birth else None,
                'gender': student.gender,
                'nationality': student.nationality,
                'district': student.district,
                'status': student.status,
                'enrollment_date': str(student.enrollment_date) if student.enrollment_date else None,
                'previous_school': student.previous_school or '',
                'index_number': student.index_number or '',
                'guardians': guardians,
            },
            'subjects': subjects,
            'attendance': attendance,
            'notes': notes,
            'overall': {
                'total_records': len(subjects),
                'teacher_comment': f'Report generated for {student.first_name} {student.last_name}.'
                                   + (f' Term: {term}.' if term else '')
                                   + (f' Year: {academic_year}.' if academic_year else ''),
            },
            'metadata': {'term': term or 'All Terms', 'academic_year': academic_year or 'All Years'},
        })


class StreamViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    serializer_class = StreamSerializer

    def get_queryset(self):
        tenant = self.get_tenant()
        return Stream.objects.filter(tenant=tenant) if tenant else Stream.objects.none()


class GuardianViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    serializer_class = GuardianSerializer

    def get_queryset(self):
        tenant = self.get_tenant()
        return Guardian.objects.filter(student__tenant=tenant) if tenant else Guardian.objects.none()


class StudentHistoryViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    serializer_class = StudentHistorySerializer

    def get_queryset(self):
        tenant = self.get_tenant()
        return StudentHistory.objects.filter(student__tenant=tenant) if tenant else StudentHistory.objects.none()


class StudentMarkViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    serializer_class = StudentMarkSerializer

    def get_queryset(self):
        tenant = self.get_tenant()
        qs = StudentMark.objects.select_related('student').filter(tenant=tenant) if tenant else StudentMark.objects.none()
        for param in ('term', 'academic_year', 'subject'):
            val = self.request.query_params.get(param)
            if val:
                qs = qs.filter(**{param: val})
        cls = self.request.query_params.get('class_assigned')
        if cls:
            qs = qs.filter(student__class_assigned=cls)
        student_id = self.request.query_params.get('student')
        if student_id:
            qs = qs.filter(student_id=student_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=self.get_tenant())

    @action(detail=False, methods=['post'], url_path='bulk-save')
    def bulk_save(self, request):
        tenant = self.get_tenant()
        items = request.data if isinstance(request.data, list) else request.data.get('marks', [])
        saved, errors = [], []
        for item in items:
            lookup = {
                'student_id': item.get('student'),
                'subject': item.get('subject'),
                'term': item.get('term'),
                'academic_year': item.get('academic_year'),
            }
            defaults = {
                'a1_score': item.get('a1_score'),
                'a2_score': item.get('a2_score'),
                'a3_score': item.get('a3_score'),
                'competency': item.get('competency', ''),
                'tenant': tenant,
            }
            try:
                obj, _ = StudentMark.objects.update_or_create(**lookup, defaults=defaults)
                saved.append(StudentMarkSerializer(obj).data)
            except Exception as e:
                errors.append({'item': item, 'error': str(e)})
        return Response({'saved': len(saved), 'errors': errors},
                        status=status.HTTP_207_MULTI_STATUS if errors else status.HTTP_200_OK)


class AttendanceViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    serializer_class = AttendanceSerializer

    def get_queryset(self):
        tenant = self.get_tenant()
        qs = Attendance.objects.select_related('student').filter(tenant=tenant) if tenant else Attendance.objects.none()
        for param in ('date', 'term', 'academic_year'):
            val = self.request.query_params.get(param)
            if val:
                qs = qs.filter(**{param: val})
        cls = self.request.query_params.get('class_assigned')
        if cls:
            qs = qs.filter(student__class_assigned=cls)
        student_id = self.request.query_params.get('student')
        if student_id:
            qs = qs.filter(student_id=student_id)
        return qs

    @action(detail=False, methods=['post'], url_path='bulk-save')
    def bulk_save(self, request):
        tenant = self.get_tenant()
        items = request.data if isinstance(request.data, list) else []
        saved, errors = [], []
        for item in items:
            lookup = {
                'student_id': item.get('student'),
                'date':       item.get('date'),
                'term':       item.get('term'),
                'academic_year': item.get('academic_year'),
            }
            defaults = {
                'status': item.get('status', 'present'),
                'note':   item.get('note', ''),
                'tenant': tenant,
            }
            try:
                obj, _ = Attendance.objects.update_or_create(**lookup, defaults=defaults)
                saved.append(obj.id)
            except Exception as e:
                errors.append({'item': item, 'error': str(e)})
        return Response(
            {'saved': len(saved), 'errors': errors},
            status=status.HTTP_207_MULTI_STATUS if errors else status.HTTP_200_OK
        )


class GeneratedReportViewSet(TenantScopedMixin, viewsets.ModelViewSet):

    def get_queryset(self):
        tenant = self.get_tenant()
        qs = GeneratedReport.objects.select_related('student').filter(tenant=tenant) if tenant else GeneratedReport.objects.none()
        for param in ('term', 'academic_year', 'template'):
            val = self.request.query_params.get(param)
            if val:
                qs = qs.filter(**{param: val})
        student_id = self.request.query_params.get('student')
        if student_id:
            qs = qs.filter(student_id=student_id)
        cls = self.request.query_params.get('class_assigned')
        if cls:
            qs = qs.filter(student__class_assigned=cls)
        return qs

    @action(detail=False, methods=['post'], url_path='bulk-save')
    def bulk_save(self, request):
        tenant = self.get_tenant()
        items = request.data if isinstance(request.data, list) else []
        saved, errors = [], []
        for item in items:
            try:
                obj, _ = GeneratedReport.objects.update_or_create(
                    student_id=item['student'],
                    term=item['term'],
                    academic_year=item['academic_year'],
                    defaults={
                        'template': item.get('template', 'modern'),
                        'report_data': item['report_data'],
                        'tenant': tenant,
                    }
                )
                # Inject the token back into report_data so the QR URL is correct
                rd = obj.report_data or {}
                rd['report_token'] = str(obj.secure_token)
                obj.report_data = rd
                obj.save(update_fields=['report_data'])
                saved.append(obj.id)
            except Exception as e:
                errors.append({'student': item.get('student'), 'error': str(e)})
        return Response(
            {'saved': len(saved), 'errors': errors},
            status=status.HTTP_207_MULTI_STATUS if errors else status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'], url_path='by-token', permission_classes=[AllowAny])
    def by_token(self, request):
        token = request.query_params.get('token', '')
        if not token:
            return Response({'error': 'token required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            report = GeneratedReport.objects.get(secure_token=token)
        except (GeneratedReport.DoesNotExist, Exception):
            return Response({'error': 'Report not found'}, status=status.HTTP_404_NOT_FOUND)
        from .serializers import GeneratedReportSerializer
        return Response(GeneratedReportSerializer(report).data)
