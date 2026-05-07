from django.utils.deprecation import MiddlewareMixin
from core.business_config import WorkerPageAccess
from tenants.models import TenantMembership

# Map page keys to API path prefixes that require the corresponding access flag
PAGE_PREFIX_MAP = {
    'dashboard_enabled': ['/api/core/analytics', '/api/core/configuration'],
    'organizations_enabled': ['/api/core/tenants/my-organizations', '/api/core/tenants/switch-tenant', '/api/core/tenants/create-organization'],
    'product_enabled': ['/api/product', '/api/core/product'],
    'inventory_enabled': ['/api/core/inventory', '/api/core/receipts', '/api/core/abandoned-carts'],
    'orders_enabled': ['/api/core/orders'],
    'customers_enabled': ['/api/core/customers'],
    'scheduling_enabled': ['/api/core/appointments'],
    'manual_entry_enabled': ['/api/core/orders'],
    'payments_enabled': ['/api/core/receipts'],
    'analytics_enabled': ['/api/core/analytics'],
    'ai_insights_enabled': ['/api/core/ai/'],
    'accounting_enabled': ['/api/accounting', '/api/school-accounting', '/api/fees'],
    'enrollment_enabled': ['/api/enrollment'],
}


class PageAccessMiddleware(MiddlewareMixin):
    """Deny API access to pages not in the worker's allowed_pages."""

    def process_request(self, request):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return None

        # Allow admins/superadmins/staff to access everything
        role = getattr(user, 'role', '')
        if role in ['tenant_admin', 'superadmin'] or getattr(user, 'is_staff', False):
            return None

        # Determine tenant for the user
        tenant = getattr(user, 'tenant', None)
        if not tenant:
            membership = TenantMembership.objects.filter(user=user).first()
            tenant = membership.tenant if membership else None
        if not tenant:
            return None

        # Load allowed pages; missing record => no access
        try:
            access = WorkerPageAccess.objects.get(tenant=tenant, user=user)
            allowed_pages = access.allowed_pages or []
        except WorkerPageAccess.DoesNotExist:
            allowed_pages = []

        # If no allowed pages, deny all mapped routes
        path = request.path
        for page_key, prefixes in PAGE_PREFIX_MAP.items():
            if any(path.startswith(prefix) for prefix in prefixes):
                if page_key not in allowed_pages:
                    from django.http import JsonResponse
                    return JsonResponse({'error': 'Access denied'}, status=403)

        return None
