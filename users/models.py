from django.db import models
from django.contrib.auth import get_user_model
from tenants.models import Tenant

User = get_user_model()


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', null=True, blank=True)
    guest_token = models.CharField(max_length=64, unique=True, null=True, blank=True)  # For guests
    name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.user:
            return f"{self.user.username}'s Profile"
        return f"Guest {self.guest_token}"

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"


class UserTenantMembership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tenant_memberships')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='user_memberships')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'tenant')
        verbose_name = 'User Tenant Membership'
        verbose_name_plural = 'User Tenant Memberships'

    def __str__(self):
        return f"{self.user.username} in {self.tenant.name}"
