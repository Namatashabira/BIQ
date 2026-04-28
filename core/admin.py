# core/admin.py
"""
Django admin configuration for core models
"""
from django.contrib import admin
from .models import Customer, Receipt, ReceiptItem, AbandonedCart, AbandonedCartItem, BusinessSettings
from .business_config import BusinessConfig, FeatureToggle, Terminology


@admin.register(BusinessConfig)
class BusinessConfigAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'business_type', 'onboarding_completed', 'preset_applied', 'created_at']
    list_filter = ['business_type', 'onboarding_completed', 'preset_applied']
    search_fields = ['tenant__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(FeatureToggle)
class FeatureToggleAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'feature_key', 'enabled', 'get_feature_display']
    list_filter = ['feature_key', 'enabled']
    search_fields = ['tenant__name']
    
    def get_feature_display(self, obj):
        return obj.get_feature_key_display()
    get_feature_display.short_description = 'Feature'


@admin.register(Terminology)
class TerminologyAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'entity', 'label', 'label_plural']
    list_filter = ['entity']
    search_fields = ['tenant__name', 'label', 'label_plural']


# Register other existing models (Order is registered in core/orders/admin.py)
admin.site.register(Customer)
admin.site.register(Receipt)
admin.site.register(ReceiptItem)
admin.site.register(AbandonedCart)
admin.site.register(AbandonedCartItem)
admin.site.register(BusinessSettings)
