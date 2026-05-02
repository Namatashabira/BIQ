from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FeeStructureViewSet, FeePaymentViewSet

router = DefaultRouter()
router.register(r'structures', FeeStructureViewSet, basename='fee-structure')
router.register(r'payments', FeePaymentViewSet, basename='fee-payment')

urlpatterns = [
    path('', include(router.urls)),
]
