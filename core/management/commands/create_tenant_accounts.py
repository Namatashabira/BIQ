# core/management/commands/create_tenant_accounts.py
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from accounts.models import ROLE_TENANT_ADMIN, ROLE_WORKER
from tenants.models import Tenant


User = get_user_model()

class Command(BaseCommand):
    help = "Create initial tenants, super admin, and worker accounts"

    def handle(self, *args, **options):
        # ----------------------------
        # 1️⃣ Create tenants
        # ----------------------------
        tenants_data = [
            {"name": "Tenant A", "slug": "tenant-a"},
            {"name": "Tenant B", "slug": "tenant-b"},
        ]

        tenants = []
        for data in tenants_data:
            tenant, created = Tenant.objects.get_or_create(
                name=data["name"],
                slug=data["slug"]
            )
            tenants.append(tenant)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created tenant: {tenant.name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Tenant already exists: {tenant.name}"))

        # ----------------------------
        # 2️⃣ Create super admin
        # ----------------------------
        super_admin_email = "superadmin@admin.com"
        if not User.objects.filter(email=super_admin_email).exists():
            super_admin = User.objects.create_superuser(
                username="superadmin",
                email=super_admin_email,
                password="SuperAdmin123!",  # change to secure password
            )
            self.stdout.write(self.style.SUCCESS("Created Super Admin"))
        else:
            self.stdout.write(self.style.WARNING("Super Admin already exists"))

        # ----------------------------
        # 3️⃣ Create sample tenant admin / worker users
        # ----------------------------
        for tenant in tenants:
            # Tenant Admin
            admin_email = f"{tenant.slug}-admin@tenant.com"
            if not User.objects.filter(email=admin_email).exists():
                User.objects.create_user(
                    username=f"{tenant.slug}-admin",
                    email=admin_email,
                    password="TenantAdmin123!",
                    tenant=tenant,
                    role=ROLE_TENANT_ADMIN,
                )
                self.stdout.write(self.style.SUCCESS(f"Created Admin for {tenant.name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Admin already exists for {tenant.name}"))

            # Worker
            worker_email = f"{tenant.slug}-worker@tenant.com"
            if not User.objects.filter(email=worker_email).exists():
                User.objects.create_user(
                    username=f"{tenant.slug}-worker",
                    email=worker_email,
                    password="TenantWorker123!",
                    tenant=tenant,
                    role=ROLE_WORKER,
                )
                self.stdout.write(self.style.SUCCESS(f"Created Worker for {tenant.name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Worker already exists for {tenant.name}"))

        self.stdout.write(self.style.SUCCESS("✅ Tenant accounts creation complete!"))
