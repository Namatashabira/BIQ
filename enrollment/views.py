from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Student, Guardian, AcademicEnrollment, Document, Fee
from .serializers import (
    StudentSerializer, GuardianSerializer, AcademicEnrollmentSerializer, DocumentSerializer, FeeSerializer
)

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
