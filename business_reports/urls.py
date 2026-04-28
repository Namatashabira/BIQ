from django.urls import path
from .views import generate_business_report

urlpatterns = [
    path("generate/", generate_business_report, name="business-report"),
]
