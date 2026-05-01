from django.contrib import admin
from .models import Plan, TenantSubscription, PaymentRequest


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['key', 'name', 'price_ugx', 'trial_days', 'product_limit', 'is_active']
    list_editable = ['is_active']


@admin.register(TenantSubscription)
class TenantSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'plan', 'status', 'trial_start', 'trial_end', 'days_left', 'is_trial_expired']
    list_filter = ['status', 'plan']
    readonly_fields = ['started_at', 'updated_at', 'is_trial_expired', 'days_left']


@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'plan', 'sender_name', 'phone_number', 'payment_method', 'transaction_id', 'status', 'activation_code', 'code_used', 'created_at']
    list_filter = ['status', 'payment_method', 'plan']
    readonly_fields = ['created_at', 'updated_at', 'activation_code', 'code_used']
    actions = ['generate_codes']

    def generate_codes(self, request, queryset):
        for pr in queryset.filter(status=PaymentRequest.STATUS_PENDING):
            pr.generate_code()
        self.message_user(request, 'Activation codes generated.')
    generate_codes.short_description = 'Generate activation codes for selected'
