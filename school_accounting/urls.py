from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'expense-categories', views.SchoolExpenseCategoryViewSet, basename='school-expense-category')
router.register(r'expenses', views.SchoolExpenseViewSet, basename='school-expense')
router.register(r'teacher-salaries', views.TeacherSalaryViewSet, basename='teacher-salary')
router.register(r'salary-receipts', views.SalaryReceiptViewSet, basename='salary-receipt')
router.register(r'income', views.SchoolIncomeViewSet, basename='school-income')
router.register(r'debts', views.SchoolDebtViewSet, basename='school-debt')
router.register(r'assets', views.SchoolAssetViewSet, basename='school-asset')
router.register(r'profit-loss', views.SchoolProfitLossViewSet, basename='school-profit-loss')
router.register(r'balance-sheet', views.SchoolBalanceSheetViewSet, basename='school-balance-sheet')

urlpatterns = [
    path('', include(router.urls)),
]
