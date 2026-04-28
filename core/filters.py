from rest_framework.filters import BaseFilterBackend
from core.models import ROLE_SUPERADMIN

class TenantFilterBackend(BaseFilterBackend):
    """
    Filters queryset by tenant based on the current authenticated user.
    Superadmin sees all tenants.
    """
    def filter_queryset(self, request, queryset, view):
        user = request.user
        if not user or not user.is_authenticated:
            return queryset.none()

        # Superadmin sees everything
        if getattr(user, 'role', None) == ROLE_SUPERADMIN:
            return queryset  # superadmin sees all tenants

        # Normal tenant
        tenant = getattr(user, "tenant", None)

        # If user has multiple memberships, pick the first tenant
        memberships = getattr(user, "tenants_memberships", None)
        if tenant is None and memberships:
            first_membership = memberships.first()
            if first_membership:
                tenant = first_membership.tenant

        if tenant is None:
            return queryset.none()

        return queryset.filter(tenant=tenant)
