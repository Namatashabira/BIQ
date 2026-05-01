from django.contrib import admin
from .models import Plan, TenantSubscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['key', 'name', 'price_ugx', 'trial_days', 'product_limit', 'is_active']
    list_editable = ['is_active']


@admin.register(TenantSubscription)
class TenantSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'plan', 'status', 'trial_start', 'trial_end', 'days_left', 'is_trial_expired']
    list_filter = ['status', 'plan']
    readonly_fields = ['started_at', 'updated_at', 'is_trial_expired', 'days_left']
