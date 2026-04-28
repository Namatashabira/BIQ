from django.urls import path
from rest_framework.routers import DefaultRouter
from .viewsets import SavedBusinessReportViewSet
from .views import (
    generate_business_report_json,
    generate_business_report_pdf,
)

router = DefaultRouter()
router.register(r'saved', SavedBusinessReportViewSet, basename='business-report')

urlpatterns = [
    path("generate/", generate_business_report_json, name="business-report-json"),
    path("generate/pdf/", generate_business_report_pdf, name="business-report-pdf"),
]
urlpatterns += router.urls
