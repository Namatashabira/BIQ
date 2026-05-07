from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError

from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify
from uuid import uuid4

from .models import Worker, Tenant
from .serializers import (
    WorkerSerializer,
    WorkerCreateSerializer,
    TenantSerializer,
    TenantCreateSerializer
)

User = get_user_model()


# ============================================================
# WORKERS MANAGEMENT
# ============================================================

class TenantWorkerViewSet(viewsets.ModelViewSet):
    """
    Manage workers inside a tenant.
    Superadmin can manage all workers.
    Tenant admin manages workers in their tenant.
    Worker can only see themselves.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = WorkerSerializer

    def get_queryset(self):
        user = self.request.user

        if user.role == "superadmin":
            return Worker.objects.all()

        if user.role == "tenant_admin" and user.tenant:
            return Worker.objects.filter(tenant=user.tenant)

        if user.role == "worker" and user.tenant:
            return Worker.objects.filter(user=user)

        return Worker.objects.none()

    def get_serializer_class(self):
        if self.action == "create":
            return WorkerCreateSerializer
        return WorkerSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user
        data = self.request.data

        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            raise ValidationError("Email and password are required")

        if User.objects.filter(email=email).exists():
            raise ValidationError({"email": "User with this email already exists"})

        # Determine tenant
        if user.role == "tenant_admin":
            tenant = user.tenant

        elif user.role == "superadmin":
            tenant_id = data.get("tenant")
            if not tenant_id:
                raise ValidationError({"tenant": "Tenant is required"})
            tenant = get_object_or_404(Tenant, id=tenant_id)

        else:
            raise PermissionDenied("Not allowed to create workers")

        # Create worker user
        worker_user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            role="worker",
            tenant=tenant
        )

        serializer.save(
            tenant=tenant,
            user=worker_user
        )

    @action(detail=True, methods=['put'], url_path='set-school-role')
    def set_school_role(self, request, pk=None):
        """Assign a school role, sync worker.pages AND WorkerPageAccess."""
        user = request.user
        if user.role not in ('tenant_admin', 'superadmin'):
            raise PermissionDenied('Not allowed')

        worker = (
            get_object_or_404(Worker, pk=pk, tenant=user.tenant)
            if user.role == 'tenant_admin'
            else get_object_or_404(Worker, pk=pk)
        )

        role = request.data.get('school_role', '')

        ROLE_PAGES = {
            'teacher':     ['marks-entry', 'attendance'],
            'bursar':      ['fees', 'school-receipt-lookup'],
            'dos':         ['student-management', 'marks-entry', 'report-templates', 'attendance'],
            'deputy':      ['student-management', 'marks-entry', 'fees', 'report-templates', 'attendance'],
            'headteacher': ['dashboard', 'student-management', 'marks-entry', 'fees',
                            'report-templates', 'attendance', 'analytics'],
            'director':    ['dashboard', 'student-management', 'marks-entry', 'fees',
                            'report-templates', 'attendance', 'analytics'],
        }

        if role not in ROLE_PAGES:
            raise ValidationError({'school_role': f'Invalid role. Must be one of: {", ".join(ROLE_PAGES.keys())}'})

        pages = ROLE_PAGES[role]

        # 1. Update Worker record
        worker.school_role = role
        worker.pages = {p: True for p in pages}
        worker.save()

        # 2. Sync WorkerPageAccess so login-based page gating also reflects the new role
        if worker.user:
            from core.business_config import WorkerPageAccess
            WorkerPageAccess.objects.update_or_create(
                tenant=worker.tenant,
                user=worker.user,
                defaults={'allowed_pages': pages}
            )

        return Response(WorkerSerializer(worker).data)

    @action(detail=True, methods=['post'], url_path='transfer-ownership')
    def transfer_ownership(self, request, pk=None):
        """Transfer tenant admin ownership to a worker. Only current tenant_admin can do this."""
        user = request.user
        if user.role not in ('tenant_admin', 'superadmin'):
            raise PermissionDenied('Only the current admin can transfer ownership')

        worker = get_object_or_404(Worker, pk=pk, tenant=user.tenant)
        if not worker.user:
            raise ValidationError('This worker has no user account yet')

        tenant = user.tenant

        with transaction.atomic():
            # Promote the worker's user to tenant_admin
            new_admin = worker.user
            new_admin.role = 'tenant_admin'
            new_admin.save(update_fields=['role'])

            # Demote the current admin to worker role
            user.role = 'worker'
            user.save(update_fields=['role'])

            # Update tenant.admin
            tenant.admin = new_admin
            tenant.save(update_fields=['admin'])

            # Give the new admin a Worker record if missing
            Worker.objects.get_or_create(tenant=tenant, user=new_admin)

        return Response({'success': True, 'message': f'Ownership transferred to {new_admin.username}'})

    @action(detail=True, methods=['put'])
    def permissions(self, request, pk=None):
        user = request.user

        if user.role == "superadmin":
            worker = get_object_or_404(Worker, pk=pk)

        elif user.role == "tenant_admin":
            worker = get_object_or_404(
                Worker,
                pk=pk,
                tenant=user.tenant
            )

        else:
            raise PermissionDenied("Not allowed")

        worker.pages = request.data.get("pages", worker.pages)
        worker.fields = request.data.get("fields", worker.fields)
        worker.save()

        return Response(WorkerSerializer(worker).data)

    def destroy(self, request, *args, **kwargs):
        user = request.user
        worker = self.get_object()

        if user.role == "superadmin":
            pass

        elif user.role == "tenant_admin" and worker.tenant == user.tenant:
            pass

        else:
            raise PermissionDenied("Not allowed to delete worker")

        if worker.user:
            worker.user.delete()

        return super().destroy(request, *args, **kwargs)


# ============================================================
# TENANT MANAGEMENT (SUPERADMIN ONLY)
# ============================================================

class TenantViewSet(viewsets.ModelViewSet):
    """
    Superadmin manages tenants.
    Tenant admin can only view their own tenant.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = TenantSerializer

    def get_queryset(self):
        user = self.request.user

        if user.role == "superadmin":
            return Tenant.objects.all()

        if user.role == "tenant_admin" and user.tenant:
            return Tenant.objects.filter(id=user.tenant.id)

        return Tenant.objects.none()

    def get_serializer_class(self):
        if self.action == "create":
            return TenantCreateSerializer
        return TenantSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Superadmin creates a tenant by providing tenant name and adminEmail.
        The system generates a 5-digit PIN as the initial password and returns it in the response.
        """
        user = request.user

        if user.role != "superadmin":
            raise PermissionDenied("Only superadmin can create tenants")

        data = request.data
        admin_email = data.get("adminEmail")
        tenant_name = data.get("name")

        if not admin_email:
            raise ValidationError({"adminEmail": "Admin email is required"})
        if not tenant_name:
            raise ValidationError({"name": "Tenant name is required"})

        if User.objects.filter(email=admin_email).exists():
            raise ValidationError({
                "adminEmail": "Admin user with this email already exists"
            })

        # Generate a 5-digit PIN (zero-padded)
        import random
        pin = str(random.randint(0, 99999)).zfill(5)

        # Generate unique path-based slug for tenant
        base_slug = slugify(tenant_name) or f"tenant-{uuid4().hex[:6]}"
        # uuid will be generated on save, so we can't use it before creation
        schema_candidate = base_slug
        counter = 1
        while Tenant.objects.filter(schema_name=schema_candidate).exists():
            schema_candidate = f"{base_slug}-{counter}"
            counter += 1
        domain_url = f"{schema_candidate}.localhost"

        # Create tenant admin user with generated PIN
        admin_user = User.objects.create_user(
            username=admin_email,
            email=admin_email,
            password=pin,
            role="tenant_admin"
        )

        # Create tenant and attach admin
        tenant = Tenant.objects.create(
            name=tenant_name,
            admin=admin_user,
            schema_name=schema_candidate,
            domain_url=domain_url,
        )


        # No Domain model present; skip domain creation for path-based routing


        # Link admin to tenant
        admin_user.tenant = tenant
        admin_user.save()

        # Build response data including the generated PIN and tenant path URL
        serializer = TenantSerializer(tenant)
        data = serializer.data
        data["initialPassword"] = pin
        # Add tenant path URL (path-based routing)
        data["tenantPath"] = f"/{tenant.path_slug}/"

        from rest_framework import status
        return Response(data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        user = request.user

        if user.role != "superadmin":
            raise PermissionDenied("Only superadmin can delete tenants")

        return super().destroy(request, *args, **kwargs)
