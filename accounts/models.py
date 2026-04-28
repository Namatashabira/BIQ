from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models

ROLE_SUPERADMIN = "superadmin"
ROLE_TENANT_ADMIN = "tenant_admin"
ROLE_WORKER = "worker"

ROLE_CHOICES = [
    (ROLE_SUPERADMIN, "Super Admin"),
    (ROLE_TENANT_ADMIN, "Tenant Admin"),
    (ROLE_WORKER, "Worker"),
]


class User(AbstractUser):
    """Shared custom user used across all schemas."""

    username_validator = RegexValidator(
        regex=r"^[\w .'+-]+$",
        message="Enter a valid username. Letters, numbers, spaces, and ./+/-/_ characters are allowed.",
    )

    username = models.CharField(
        max_length=150,
        unique=True,
        help_text="Required. 150 characters or fewer. Letters, digits, spaces and ./+/-/_ only.",
        validators=[username_validator],
        error_messages={"unique": "A user with that username already exists."},
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_WORKER,
        help_text="User role in the system",
    )
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )
    phone = models.CharField(max_length=20, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)

    @property
    def is_tenant_verified(self):
        return self.tenant and getattr(self.tenant, "is_verified", False)
