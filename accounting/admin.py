from django.contrib import admin
from .models import (
    ExpenseCategory, Expense, Payment, Tax, 
    Asset, Liability, Equity, AuditLog
)


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'created_at']
    list_filter = ['tenant', 'created_at']
    search_fields = ['name', 'description']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ['date', 'vendor', 'amount', 'category', 'payment_method', 'tenant']
    list_filter = ['tenant', 'date', 'category', 'payment_method', 'is_recurring']
    search_fields = ['vendor', 'notes']
    date_hierarchy = 'date'


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['date', 'party_name', 'amount', 'payment_type', 'status', 'tenant']
    list_filter = ['tenant', 'payment_type', 'status', 'date']
    search_fields = ['party_name', 'reference_number', 'notes']
    date_hierarchy = 'date'


@admin.register(Tax)
class TaxAdmin(admin.ModelAdmin):
    list_display = ['tax_type', 'amount', 'due_date', 'status', 'tenant']
    list_filter = ['tenant', 'tax_type', 'status', 'due_date']
    search_fields = ['notes', 'payment_reference']
    date_hierarchy = 'due_date'


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ['name', 'asset_type', 'value', 'tenant']
    list_filter = ['tenant', 'asset_type']
    search_fields = ['name', 'notes']


@admin.register(Liability)
class LiabilityAdmin(admin.ModelAdmin):
    list_display = ['name', 'liability_type', 'amount', 'due_date', 'tenant']
    list_filter = ['tenant', 'liability_type']
    search_fields = ['name', 'notes']


@admin.register(Equity)
class EquityAdmin(admin.ModelAdmin):
    list_display = ['equity_type', 'amount', 'date', 'tenant']
    list_filter = ['tenant', 'equity_type', 'date']
    search_fields = ['notes']
    date_hierarchy = 'date'


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'user', 'action', 'model_type', 'object_repr', 'ip_address', 'is_suspicious']
    list_filter = ['action', 'model_type', 'is_suspicious', 'timestamp', 'tenant']
    search_fields = ['user__username', 'user__email', 'object_repr', 'ip_address']
    readonly_fields = ['tenant', 'user', 'action', 'model_type', 'object_id', 'object_repr', 
                       'changes', 'ip_address', 'user_agent', 'endpoint', 'method', 'timestamp']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    
    def has_add_permission(self, request):
        # Audit logs cannot be manually created
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Audit logs cannot be deleted to maintain integrity
        return False
    
    def has_change_permission(self, request, obj=None):
        # Only allow marking suspicious or adding notes
        return request.user.is_superuser

