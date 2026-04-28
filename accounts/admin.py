from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "Tenant Access",
            {
                "fields": (
                    "role",
                    "tenant",
                    "phone",
                    "location",
                )
            },
        ),
    )
    list_display = (
        "username",
        "email",
        "role",
        "tenant",
        "is_staff",
        "is_active",
    )
    list_filter = (
        "role",
        "tenant",
        "is_staff",
        "is_superuser",
        "is_active",
    )
