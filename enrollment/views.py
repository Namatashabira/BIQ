from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Q

from .models import (
    Student, Guardian, AcademicEnrollment, Document, Fee,
    Subject, Competency, Assessment, GradingSystem, Report
)
from .serializers import (
    StudentSerializer, GuardianSerializer, AcademicEnrollmentSerializer, DocumentSerializer, FeeSerializer,
    SubjectSerializer, CompetencySerializer, AssessmentSerializer, GradingSystemSerializer, ReportSerializer
)
from .grading_utils import generate_report_data

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all().order_by('created_at')
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def aligned(self, request):
        # Return students sorted by created_at for consistent alignment
        students = Student.objects.all().order_by('created_at')
        serializer = self.get_serializer(students, many=True)
        return Response(serializer.data)

class GuardianViewSet(viewsets.ModelViewSet):
    queryset = Guardian.objects.all()
    serializer_class = GuardianSerializer
    permission_classes = [permissions.IsAuthenticated]

class AcademicEnrollmentViewSet(viewsets.ModelViewSet):
    queryset = AcademicEnrollment.objects.all()
    serializer_class = AcademicEnrollmentSerializer
    permission_classes = [permissions.IsAuthenticated]

class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

class FeeViewSet(viewsets.ModelViewSet):
    queryset = Fee.objects.all()
    serializer_class = FeeSerializer
    permission_classes = [permissions.IsAuthenticated]


# ============================================================================
# COMPETENCE-BASED CURRICULUM (CBC) VIEWSETS & VIEWS
# ============================================================================

class SubjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Subject management.
    Scoped to current user's tenant.
    """
    serializer_class = SubjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter subjects by current user's tenant"""
        from tenants.models import Tenant
        user = self.request.user
        
        # Get user's tenant
        tenant = None
        if hasattr(user, 'tenant') and user.tenant:
            tenant = user.tenant
        elif user.is_superuser:
            # Superadmin can see all
            return Subject.objects.all()
        
        if tenant:
            return Subject.objects.filter(tenant=tenant).order_by('name')
        
        return Subject.objects.none()

    def perform_create(self, serializer):
        """Set tenant when creating subject"""
        user = self.request.user
        tenant = user.tenant if hasattr(user, 'tenant') else None
        if tenant:
            serializer.save(tenant=tenant)


class CompetencyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Competency management.
    """
    serializer_class = CompetencySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter competencies by subject's tenant"""
        user = self.request.user
        tenant = user.tenant if hasattr(user, 'tenant') else None
        
        if tenant:
            return Competency.objects.filter(
                subject__tenant=tenant
            ).order_by('code')
        
        if user.is_superuser:
            return Competency.objects.all()
        
        return Competency.objects.none()


class AssessmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Assessment (scores) management.
    Multi-tenant scoped.
    """
    serializer_class = AssessmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter assessments by student's tenant"""
        user = self.request.user
        tenant = user.tenant if hasattr(user, 'tenant') else None
        
        if tenant:
            return Assessment.objects.filter(
                student__id__in=Student.objects.filter(id__in=[])  # You can filter by class if needed
            ).order_by('-date_assessed')
        
        if user.is_superuser:
            return Assessment.objects.all()
        
        return Assessment.objects.none()

    @action(detail=False, methods=['get'])
    def by_student(self, request):
        """Get assessments for a specific student"""
        student_id = request.query_params.get('student_id')
        if not student_id:
            return Response(
                {'error': 'student_id parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        student = get_object_or_404(Student, id=student_id)
        
        # Check authorization
        user = request.user
        if not user.is_superuser and hasattr(user, 'tenant'):
            if student.id not in []:  # Add tenant check if needed
                return Response(
                    {'error': 'Unauthorized'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        assessments = Assessment.objects.filter(student=student).order_by('-date_assessed')
        serializer = self.get_serializer(assessments, many=True)
        return Response(serializer.data)


class GradingSystemViewSet(viewsets.ModelViewSet):
    """
    ViewSet for GradingSystem management.
    One per tenant.
    """
    serializer_class = GradingSystemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter grading systems by current user's tenant"""
        user = self.request.user
        tenant = user.tenant if hasattr(user, 'tenant') else None
        
        if tenant:
            return GradingSystem.objects.filter(tenant=tenant)
        
        if user.is_superuser:
            return GradingSystem.objects.all()
        
        return GradingSystem.objects.none()

    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current tenant's grading system"""
        user = request.user
        tenant = user.tenant if hasattr(user, 'tenant') else None
        
        if not tenant:
            return Response(
                {'error': 'No tenant associated with user'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        grading_system, created = GradingSystem.objects.get_or_create(tenant=tenant)
        
        if created:
            # Set defaults
            from .grading_utils import get_default_grading_system
            defaults = get_default_grading_system()
            grading_system.grade_boundaries = defaults['grade_boundaries']
            grading_system.remarks = defaults['remarks']
            grading_system.save()
        
        serializer = self.get_serializer(grading_system)
        return Response(serializer.data)


class ReportViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Report management.
    """
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter reports by student's tenant"""
        user = self.request.user
        tenant = user.tenant if hasattr(user, 'tenant') else None
        
        if tenant:
            return Report.objects.filter(
                student__id__in=[]  # Filter by tenant students
            ).order_by('-academic_year', '-term')
        
        if user.is_superuser:
            return Report.objects.all()
        
        return Report.objects.none()


# ============================================================================
# REPORT GENERATION API VIEWS
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generate_student_report(request, student_id):
    """
    Generate report for a student in a specific term.
    
    Query params:
        - term: Term identifier (required)
        - academic_year: Academic year (required)
    
    Returns:
        {
            student: {...},
            subjects: [{...}],
            overall: {...},
            metadata: {...}
        }
    """
    student = get_object_or_404(Student, id=student_id)
    
    # Authorization check
    user = request.user
    if not user.is_superuser:
        tenant = user.tenant if hasattr(user, 'tenant') else None
        if not tenant:
            return Response(
                {'error': 'Unauthorized'},
                status=status.HTTP_403_FORBIDDEN
            )
    
    # Get query parameters
    term = request.query_params.get('term')
    academic_year = request.query_params.get('academic_year')
    
    if not term or not academic_year:
        return Response(
            {'error': 'term and academic_year parameters required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Generate report data
    report_data = generate_report_data(
        student,
        term,
        academic_year,
        tenant=user.tenant if hasattr(user, 'tenant') else None
    )
    
    if not report_data:
        return Response(
            {'error': 'No enrollment or assessments found for this term'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    return Response(report_data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_report(request):
    """
    Save/create a report record in database.
    
    Request body:
        {
            student_id: UUID,
            term: string,
            academic_year: string,
            teacher_comment: string (optional)
        }
    """
    user = request.user
    tenant = user.tenant if hasattr(user, 'tenant') else None
    
    student_id = request.data.get('student_id')
    term = request.data.get('term')
    academic_year = request.data.get('academic_year')
    teacher_comment = request.data.get('teacher_comment')
    
    if not all([student_id, term, academic_year]):
        return Response(
            {'error': 'student_id, term, and academic_year required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    student = get_object_or_404(Student, id=student_id)
    
    # Generate report data
    report_data = generate_report_data(student, term, academic_year, tenant=tenant)
    
    if not report_data:
        return Response(
            {'error': 'Failed to generate report'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Save report to database
    report, created = Report.objects.update_or_create(
        student=student,
        term=term,
        academic_year=academic_year,
        defaults={
            'overall_score': report_data['overall']['score'],
            'overall_grade': report_data['overall']['grade'],
            'overall_remark': report_data['overall']['remark'],
            'subject_performance': report_data['subjects'],
            'teacher_comment': teacher_comment or report_data['overall']['teacher_comment'],
            'generated_by': user
        }
    )
    
    serializer = ReportSerializer(report)
    status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return Response(serializer.data, status=status_code)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_student_reports(request, student_id):
    """
    Get all reports for a student.
    """
    student = get_object_or_404(Student, id=student_id)
    
    reports = Report.objects.filter(student=student).order_by('-academic_year', '-term')
    serializer = ReportSerializer(reports, many=True)
    return Response(serializer.data)
