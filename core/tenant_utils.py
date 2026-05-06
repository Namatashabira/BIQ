"""Shared utility to resolve the tenant from a request user."""
from tenants.models import TenantMembership, Tenant


def get_tenant_for_user(user):
    """
    Returns the Tenant for the given user.
    - If user is a tenant admin, returns their tenant directly.
    - If user is a worker/member, returns the tenant they belong to.
    - Returns None if no tenant found.
    """
    if not user or not user.is_authenticated:
        return None
    # Check if user is a tenant admin
    try:
        return user.tenant_admin
    except Tenant.DoesNotExist:
        pass
    # Check membership
    membership = TenantMembership.objects.filter(user=user).select_related('tenant').first()
    if membership:
        return membership.tenant
    return None
