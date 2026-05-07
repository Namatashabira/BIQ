from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StudentViewSet, StreamViewSet, GuardianViewSet, StudentHistoryViewSet, StudentMarkViewSet, GeneratedReportViewSet, AttendanceViewSet

router = DefaultRouter()
router.register(r'students', StudentViewSet, basename='student')
router.register(r'streams', StreamViewSet, basename='stream')
router.register(r'guardians', GuardianViewSet, basename='guardian')
router.register(r'student-history', StudentHistoryViewSet, basename='student-history')
router.register(r'marks', StudentMarkViewSet, basename='student-mark')
router.register(r'generated-reports', GeneratedReportViewSet, basename='generated-report')
router.register(r'attendance', AttendanceViewSet, basename='attendance')

urlpatterns = [
    path('', include(router.urls)),
]
