from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'students', views.StudentViewSet, basename='student')
router.register(r'guardians', views.GuardianViewSet, basename='guardian')
router.register(r'enrollments', views.AcademicEnrollmentViewSet, basename='enrollment')
router.register(r'documents', views.DocumentViewSet, basename='document')
router.register(r'fees', views.FeeViewSet, basename='fee')

urlpatterns = [
    path('', include(router.urls)),
]
