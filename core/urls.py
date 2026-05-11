from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SuperAdminTenantSummaryView,
    BusinessSettingsView,
    CustomerView,
    ReceiptView,
    AbandonedCartView,
    AppointmentView,
    WorkerListView,
)
from .auth_views import (
    login, logout, user_profile,
    request_password_reset, verify_reset_token, confirm_password_reset,
    get_business_types
)
from .auth_views import register
from .tenant_views import (
    get_my_organizations,
    switch_tenant,
    create_organization
)
from .analytics_views import analytics_summary
from .views_config import (
    BusinessConfigViewSet,
    FeatureToggleViewSet,
    TerminologyViewSet,
    ThemeViewSet,
    PricingSettingsView,
    get_business_presets,
    get_configuration_summary,
    complete_onboarding,
    WorkerAccessInviteView,
    WorkerAccessActivateView,
    WorkerAccessCheckOtpView,
    WorkerPageAccessView,
    StaffCredentialsView,
)
from .views_ai import (
    ai_sales_forecast,
    ai_inventory_optimization,
    ai_customer_behavior,
    ai_profit_prediction,
    ai_comprehensive_insights
)
from .views_openai import (
    openai_business_insights,
    openai_product_recommendations,
    openai_inventory_strategy,
    openai_customer_message,
    openai_sales_analysis
)

# Router for viewsets
router = DefaultRouter()
router.register(r'business-config', BusinessConfigViewSet, basename='business-config')
router.register(r'feature-toggles', FeatureToggleViewSet, basename='feature-toggles')
router.register(r'terminology', TerminologyViewSet, basename='terminology')
router.register(r'theme', ThemeViewSet, basename='theme')

urlpatterns = [
    # Configuration endpoints
    path('', include(router.urls)),
    path('business-presets/', get_business_presets, name='business-presets'),
    path('configuration/', get_configuration_summary, name='configuration-summary'),
    path('configuration/complete-onboarding/', complete_onboarding, name='complete-onboarding'),
    path('pricing-settings/', PricingSettingsView.as_view(), name='pricing-settings'),
    path('access/invite/', WorkerAccessInviteView.as_view(), name='access-invite'),
    path('access/activate/', WorkerAccessActivateView.as_view(), name='access-activate'),
    path('access/check-otp/', WorkerAccessCheckOtpView.as_view(), name='access-check-otp'),
    path('access/pages/', WorkerPageAccessView.as_view(), name='access-pages'),
    path('staff-credentials/', StaffCredentialsView.as_view(), name='staff-credentials'),
    
    # Existing endpoints
    path('superadmin-summary/', SuperAdminTenantSummaryView.as_view(), name='superadmin-summary'),
    path('analytics/', analytics_summary, name='analytics'),
    path('business-settings/', BusinessSettingsView.as_view(), name='business-settings'),
    path('customers/', CustomerView.as_view(), name='customers'),
    path('receipts/', ReceiptView.as_view(), name='receipts'),
    path('abandoned-carts/', AbandonedCartView.as_view(), name='abandoned-carts'),
    path('appointments/', AppointmentView.as_view(), name='appointments'),
    path('workers/', WorkerListView.as_view(), name='workers'),
    path('auth/business-types/', get_business_types, name='business-types'),
    path('auth/register/', register, name='register'),
    path('auth/login/', login, name='login'),
    path('auth/logout/', logout, name='logout'),
    path('auth/profile/', user_profile, name='user-profile'),
    path('health/', lambda request: __import__('django.http', fromlist=['JsonResponse']).JsonResponse({'status': 'ok'}), name='health'),
    path('auth/password-reset/request/', request_password_reset, name='password-reset-request'),
    path('auth/password-reset/verify/', verify_reset_token, name='password-reset-verify'),
    path('auth/password-reset/confirm/', confirm_password_reset, name='password-reset-confirm'),
    
    # Tenant management endpoints
    path('tenants/my-organizations/', get_my_organizations, name='my-organizations'),
    path('tenants/switch-tenant/', switch_tenant, name='switch-tenant'),
    path('tenants/create-organization/', create_organization, name='create-organization'),
    
    # AI Analytics endpoints (NumPy-based)
    path('ai/sales-forecast/', ai_sales_forecast, name='ai-sales-forecast'),
    path('ai/inventory-optimization/', ai_inventory_optimization, name='ai-inventory-optimization'),
    path('ai/customer-behavior/', ai_customer_behavior, name='ai-customer-behavior'),
    path('ai/profit-prediction/', ai_profit_prediction, name='ai-profit-prediction'),
    path('ai/comprehensive-insights/', ai_comprehensive_insights, name='ai-comprehensive-insights'),
    
    # OpenAI-powered endpoints (GPT-based suggestions)
    path('openai/business-insights/', openai_business_insights, name='openai-business-insights'),
    path('openai/product-recommendations/', openai_product_recommendations, name='openai-product-recommendations'),
    path('openai/inventory-strategy/', openai_inventory_strategy, name='openai-inventory-strategy'),
    path('openai/customer-message/', openai_customer_message, name='openai-customer-message'),
    path('openai/sales-analysis/', openai_sales_analysis, name='openai-sales-analysis'),
]
