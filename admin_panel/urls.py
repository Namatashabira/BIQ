from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    # Admin panel
    path('admin/', admin.site.urls),

    # JWT authentication
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Core app: Orders
    # - /api/core/user/orders/ → POST by customers
    # - /api/core/orders/ → GET for admin dashboard
    # - /api/core/superadmin-summary/ → optional superadmin summary
    path('api/core/', include('core.orders.urls')),
    # Core app: All core endpoints (auth, config, etc.)
    path('api/core/', include('core.urls')),

    # Tenants app: workers, tenant access management
    path('api/tenants/', include('tenants.urls')),

    # Users app: user profiles and information
    path('api/users/', include('users.urls')),
    
    # Product app: product management
    path('api/products/', include('product.urls')),
    
    # Accounting app: expenses, payments, taxes, P&L, balance sheet
    path('api/accounting/', include('accounting.urls')),

    # Website Config app: order sync endpoints
    path('api/website-config/', include('website_config.urls')),

    # Forecast app: sales forecasting
    path('api/forecast/', include('forecast.urls')),
    
    # Sales app: sales analytics and dashboard
    path('api/sales/', include('sales.urls')),

    # Business Reports app
    path('api/reports/', include('business_reports.api.urls')),

    # Plans & Subscriptions
    path('api/plans/', include('plans.urls')),

    # Students management
    path('api/school/', include('students.urls')),

    # Fees management
    path('api/fees/', include('fees.urls')),

    # Schools: marks entry, report cards
    path('schools/', include('schools.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
