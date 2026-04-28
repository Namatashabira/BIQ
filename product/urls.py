# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet
from .dashboard_views import dashboard_stats, stock_history

router = DefaultRouter()
router.register(r'', ProductViewSet, basename='product')

urlpatterns = [
    path('dashboard/stats/', dashboard_stats, name='dashboard-stats'),
    path('dashboard/stock-history/', stock_history, name='stock-history'),
    path('', include(router.urls)),
]
