from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'students', views.StudentViewSet, basename='student')
router.register(r'guardians', views.GuardianViewSet, basename='guardian')
router.register(r'enrollments', views.AcademicEnrollmentViewSet, basename='enrollment')
router.register(r'documents', views.DocumentViewSet, basename='document')
router.register(r'fees', views.FeeViewSet, basename='fee')
router.register(r'subjects', views.SubjectViewSet, basename='subject')
router.register(r'competencies', views.CompetencyViewSet, basename='competency')
router.register(r'assessments', views.AssessmentViewSet, basename='assessment')
router.register(r'grading-systems', views.GradingSystemViewSet, basename='grading-system')
router.register(r'reports', views.ReportViewSet, basename='report')

urlpatterns = [
    path('', include(router.urls)),
    # Report generation endpoints
    path('students/<uuid:student_id>/report/', views.generate_student_report, name='generate-student-report'),
    path('students/<uuid:student_id>/reports/', views.get_student_reports, name='get-student-reports'),
    path('reports/save/', views.save_report, name='save-report'),
]
