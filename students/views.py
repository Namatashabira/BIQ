from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .models import Student, Stream, Guardian, StudentHistory, StudentMark, GeneratedReport, CLASS_CHOICES
from .serializers import (
    StudentSerializer, StreamSerializer,
    GuardianSerializer, StudentHistorySerializer, StudentMarkSerializer,
    GeneratedReportSerializer,
)


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.select_related('stream').prefetch_related('guardians', 'history').all()
    serializer_class = StudentSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @action(detail=False, methods=['get'], url_path='meta')
    def meta(self, request):
        return Response({
            'classes': [{'value': v, 'label': l} for v, l in CLASS_CHOICES],
            'streams': StreamSerializer(Stream.objects.all(), many=True).data,
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
        """
        Generate a simple report from StudentHistory performance records.
        Query params: term (optional), academic_year (optional)
        """
        student = self.get_object()
        term = request.query_params.get('term', '')
        academic_year = request.query_params.get('academic_year', '')

        qs = student.history.filter(history_type='performance')
        if term:
            qs = qs.filter(title__icontains=term)
        if academic_year:
            qs = qs.filter(date__year=academic_year)

        records = list(qs.order_by('-date'))

        subjects = []
        for r in records:
            subjects.append({
                'subject_name': r.title,
                'subject_code': r.title[:6].upper(),
                'score': 0,
                'grade': '—',
                'remark': r.description or '',
                'date': str(r.date),
                'competencies': [],
            })

        # Attendance summary
        attendance = list(student.history.filter(history_type='attendance').order_by('-date').values(
            'title', 'description', 'date'
        ))

        # Notes
        notes = list(student.history.filter(history_type='note').order_by('-date').values(
            'title', 'description', 'date'
        ))

        guardians = [{
            'full_name': g.full_name,
            'relationship': g.relationship,
            'phone': g.phone,
            'email': g.email or '',
        } for g in student.guardians.all()]

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
                'total_records': len(records),
                'teacher_comment': f'Report generated for {student.first_name} {student.last_name}.'
                                   + (f' Term: {term}.' if term else '')
                                   + (f' Year: {academic_year}.' if academic_year else ''),
            },
            'metadata': {
                'term': term or 'All Terms',
                'academic_year': academic_year or 'All Years',
            },
        })


class StreamViewSet(viewsets.ModelViewSet):
    queryset = Stream.objects.all()
    serializer_class = StreamSerializer


class GuardianViewSet(viewsets.ModelViewSet):
    queryset = Guardian.objects.all()
    serializer_class = GuardianSerializer


class StudentHistoryViewSet(viewsets.ModelViewSet):
    queryset = StudentHistory.objects.all()
    serializer_class = StudentHistorySerializer


class StudentMarkViewSet(viewsets.ModelViewSet):
    serializer_class = StudentMarkSerializer

    def get_queryset(self):
        qs = StudentMark.objects.select_related('student').all()
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

    @action(detail=False, methods=['post'], url_path='bulk-save')
    def bulk_save(self, request):
        """Upsert a list of marks. Each item needs student, subject, term, academic_year."""
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
                'ca_score': item.get('ca_score'),
                'exam_score': item.get('exam_score'),
                'competency': item.get('competency', ''),
            }
            try:
                obj, _ = StudentMark.objects.update_or_create(**lookup, defaults=defaults)
                saved.append(StudentMarkSerializer(obj).data)
            except Exception as e:
                errors.append({'item': item, 'error': str(e)})
        return Response({'saved': len(saved), 'errors': errors},
                        status=status.HTTP_207_MULTI_STATUS if errors else status.HTTP_200_OK)


class GeneratedReportViewSet(viewsets.ModelViewSet):
    serializer_class = GeneratedReportSerializer
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = GeneratedReport.objects.select_related('student').all()
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
        """Upsert multiple report snapshots at once.
        Payload: list of {student, term, academic_year, template, report_data}
        """
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
                    }
                )
                saved.append(obj.id)
            except Exception as e:
                errors.append({'student': item.get('student'), 'error': str(e)})
        return Response(
            {'saved': len(saved), 'errors': errors},
            status=status.HTTP_207_MULTI_STATUS if errors else status.HTTP_200_OK
        )
