from django.urls import path
from .views import SalesDashboardAPIView, SalesTrendAPIView

app_name = 'sales'

urlpatterns = [
    path('dashboard/', SalesDashboardAPIView.as_view(), name='sales-dashboard'),
    path('trend/', SalesTrendAPIView.as_view(), name='sales-trend'),
]