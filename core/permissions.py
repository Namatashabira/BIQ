from rest_framework import permissions
from core.models import ROLE_SUPERADMIN, ROLE_TENANT_ADMIN, ROLE_WORKER

class IsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated and 
            (request.user.is_superuser or getattr(request.user, 'role', None) == ROLE_SUPERADMIN)
        )

class IsTenantAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated and 
            getattr(request.user, 'role', None) in [ROLE_SUPERADMIN, ROLE_TENANT_ADMIN]
        )

class IsWorker(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated and 
            getattr(request.user, 'role', None) in [ROLE_SUPERADMIN, ROLE_TENANT_ADMIN, ROLE_WORKER]
        )

class IsTenantMember(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated and 
            (getattr(request.user, 'tenant', None) is not None or 
             getattr(request.user, 'role', None) == ROLE_SUPERADMIN)
        )

class IsAdminOrReadOnly(permissions.BasePermission):
    """Allow read access to all authenticated users, write access to admins only"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.method in permissions.SAFE_METHODS:
            return True
            
        return getattr(request.user, 'role', None) in [ROLE_SUPERADMIN, ROLE_TENANT_ADMIN]
