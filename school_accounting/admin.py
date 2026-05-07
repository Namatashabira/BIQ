from django.contrib import admin
from .models import (
    SchoolExpenseCategory, SchoolExpense, TeacherSalary,
    SchoolIncome, SchoolDebt, SchoolAsset
)


@admin.register(SchoolExpenseCategory)
class SchoolExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category_type', 'tenant', 'created_at']
    list_filter = ['category_type', 'tenant']
    search_fields = ['name', 'description']


@admin.register(SchoolExpense)
class SchoolExpenseAdmin(admin.ModelAdmin):
    list_display = ['date', 'description', 'amount', 'category', 'payee', 'payment_method', 'tenant']
    list_filter = ['date', 'category', 'payment_method', 'term', 'academic_year', 'tenant']
    search_fields = ['description', 'payee', 'reference_number']
    date_hierarchy = 'date'


@admin.register(TeacherSalary)
class TeacherSalaryAdmin(admin.ModelAdmin):
    list_display = ['teacher_name', 'month', 'net_salary', 'amount_paid', 'status', 'payment_date', 'tenant']
    list_filter = ['status', 'month', 'payment_method', 'tenant']
    search_fields = ['teacher_name', 'employee_id', 'reference_number']
    date_hierarchy = 'month'


@admin.register(SchoolIncome)
class SchoolIncomeAdmin(admin.ModelAdmin):
    list_display = ['date', 'description', 'amount', 'income_type', 'source', 'payment_method', 'tenant']
    list_filter = ['date', 'income_type', 'payment_method', 'term', 'academic_year', 'tenant']
    search_fields = ['description', 'source', 'reference_number']
    date_hierarchy = 'date'


@admin.register(SchoolDebt)
class SchoolDebtAdmin(admin.ModelAdmin):
    list_display = ['creditor_name', 'debt_type', 'original_amount', 'balance', 'status', 'due_date', 'tenant']
    list_filter = ['status', 'debt_type', 'incurred_date', 'due_date', 'tenant']
    search_fields = ['creditor_name', 'description']
    date_hierarchy = 'incurred_date'


@admin.register(SchoolAsset)
class SchoolAssetAdmin(admin.ModelAdmin):
    list_display = ['name', 'asset_type', 'purchase_value', 'current_value', 'purchase_date', 'condition', 'tenant']
    list_filter = ['asset_type', 'purchase_date', 'condition', 'tenant']
    search_fields = ['name', 'location']
    date_hierarchy = 'purchase_date'
