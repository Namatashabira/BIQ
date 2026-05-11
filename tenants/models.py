
import uuid
from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

User = settings.AUTH_USER_MODEL


class Tenant(models.Model):
    # Unique UUID for tenant isolation
    uuid = models.UUIDField(default=uuid.uuid4, null=False, blank=False, unique=True, editable=False, help_text='Globally unique tenant ID')
    """Tenant/Account model for multi-organization support (single database)."""
    name = models.CharField(max_length=255)
    @property
    def path_slug(self):
        from django.utils.text import slugify
        return f"{slugify(self.name)}-{str(self.uuid)[:8]}"
    admin = models.OneToOneField(User, on_delete=models.CASCADE, related_name="tenant_admin")
    BUSINESS_TYPE_CHOICES = [
        ('retail', 'Retail / Shop'),
        ('wholesale', 'Wholesale / Distribution'),
        ('supermarket', 'Supermarket / Grocery'),
        ('restaurant', 'Restaurant / Food & Beverage'),
        ('manufacturing', 'Manufacturing'),
        ('services', 'Service Business'),
        ('healthcare', 'Health / Medical'),
        ('school', 'Education / School'),
        ('agrobusiness', 'Agriculture / Agribusiness'),
        ('hardware', 'Hardware / Construction'),
        ('transportation', 'Transportation / Logistics'),
        ('ecommerce', 'E-commerce / Online Business'),
        ('nonprofit', 'Non-Profit / NGO'),
        ('other', 'Other'),
    ]
    business_type = models.CharField(
        max_length=50,
        choices=BUSINESS_TYPE_CHOICES,
        default='other',
        help_text='Type of business for this tenant (controls auto-configuration)'
    )

    # Optional fields for multi-tenancy
    schema_name = models.CharField(max_length=64, null=True, blank=True, help_text='Schema name for multi-tenancy (optional)')
    domain_url = models.CharField(max_length=255, null=True, blank=True, help_text='Domain URL for tenant (optional)')

    SCHOOL_TYPE_CHOICES = [
        ('primary', 'Primary School'),
        ('secondary', 'Secondary School'),
    ]
    school_type = models.CharField(
        max_length=20,
        choices=SCHOOL_TYPE_CHOICES,
        blank=True,
        default='',
        help_text='Only applicable when business_type is school'
    )

    is_verified = models.BooleanField(default=False, help_text='Tenant account must be verified to access system')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name}"


class Worker(models.Model):
    SCHOOL_ROLE_CHOICES = [
        ('teacher',     'Teacher'),
        ('bursar',      'Bursar'),
        ('dos',         'Director of Studies (DOS)'),
        ('deputy',      'Deputy Headteacher'),
        ('headteacher', 'Headteacher'),
        ('director',    'Director'),
    ]
    tenant      = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="workers")
    user        = models.OneToOneField(User, on_delete=models.CASCADE, related_name="worker_profile", null=True, blank=True)
    school_role = models.CharField(max_length=20, choices=SCHOOL_ROLE_CHOICES, blank=True, default='')
    pages       = models.JSONField(default=dict)
    fields      = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.tenant.name} Worker"


class TenantMembership(models.Model):
    """Optional separate membership model to allow users to belong to multiple tenants."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="tenants_memberships"
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="members"
    )
    role = models.CharField(max_length=50, default="member")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'tenant')
        verbose_name = "Tenant Membership"
        verbose_name_plural = "Tenant Memberships"

    def __str__(self):
        return f"{self.user.email} in {self.tenant.name} as {self.role}"


@receiver(post_save, sender=Tenant)
def auto_configure_features_on_tenant_creation(sender, instance, created, **kwargs):
    """After a Tenant is created, auto-configure feature toggles based on business_type."""
    if created:
        import uuid as uuid_lib
        from django.contrib.auth import get_user_model
        all_pages = [
            "Dashboard", "Analytics", "Appointments", "Customers", "Inventory", "ManualEntry", "ManualOrderEntry", "Orders", "Product", "Products", "ReceiptLookup", "Sales", "Settings", "UserProducts"
        ]
        # Create or update the admin's Worker record
        admin_user = instance.admin
        from .models import Worker
        worker, created_worker = Worker.objects.get_or_create(
            tenant=instance,
            # If you have a user field in Worker, add user=admin_user here
        )
        worker.pages = {name: {"uuid": str(uuid_lib.uuid4())} for name in all_pages}
        worker.save(update_fields=["pages"])
        TenantMembership.objects.get_or_create(
            user=admin_user,
            tenant=instance,
            defaults={"role": "admin"}
        )
