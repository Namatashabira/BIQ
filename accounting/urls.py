from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'expense-categories', views.ExpenseCategoryViewSet, basename='expense-category')
router.register(r'expenses', views.ExpenseViewSet, basename='expense')
router.register(r'payments', views.PaymentViewSet, basename='payment')
router.register(r'taxes', views.TaxViewSet, basename='tax')
router.register(r'assets', views.AssetViewSet, basename='asset')
router.register(r'liabilities', views.LiabilityViewSet, basename='liability')
router.register(r'equity', views.EquityViewSet, basename='equity')
router.register(r'audit-logs', views.AuditLogViewSet, basename='audit-log')
router.register(r'profit-loss', views.ProfitLossViewSet, basename='profit-loss')
router.register(r'balance-sheet', views.BalanceSheetViewSet, basename='balance-sheet')

urlpatterns = [
    path('', include(router.urls)),
]
