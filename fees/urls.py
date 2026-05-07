from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FeeStructureViewSet, FeeItemViewSet, FeePaymentViewSet, FeeItemPaymentViewSet, receipt_settings_view, public_receipt_lookup

router = DefaultRouter()
router.register(r'structures', FeeStructureViewSet, basename='fee-structure')
router.register(r'items', FeeItemViewSet, basename='fee-item')
router.register(r'payments', FeePaymentViewSet, basename='fee-payment')
router.register(r'item-payments', FeeItemPaymentViewSet, basename='fee-item-payment')

urlpatterns = [
    path('', include(router.urls)),
    path('receipt-settings/', receipt_settings_view, name='receipt-settings'),
    path('receipt/<str:receipt_number>/', public_receipt_lookup, name='public-receipt-lookup'),
]
