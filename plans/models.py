from django.db import models
from django.utils import timezone
from datetime import timedelta
from tenants.models import Tenant


class Plan(models.Model):
    PLAN_KEYS = [
        ('free', 'Free Trial'),
        ('starter', 'Starter'),
        ('business', 'Business'),
        ('enterprise', 'Enterprise'),
    ]

    key = models.CharField(max_length=20, choices=PLAN_KEYS, unique=True)
    name = models.CharField(max_length=100)
    price_ugx = models.PositiveIntegerField(default=0, help_text='Monthly price in UGX')
    trial_days = models.PositiveIntegerField(default=0, help_text='0 = no trial')
    product_limit = models.IntegerField(default=7, help_text='-1 = unlimited')
    allowed_pages = models.JSONField(
        default=list,
        help_text='List of page keys allowed. Empty list = all pages.'
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    @property
    def product_limit_display(self):
        return 'Unlimited' if self.product_limit == -1 else self.product_limit


class TenantSubscription(models.Model):
    STATUS_TRIAL = 'trial'
    STATUS_ACTIVE = 'active'
    STATUS_EXPIRED = 'expired'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_TRIAL, 'Trial'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_TRIAL)
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.tenant.name} — {self.plan.name} ({self.status})"

    @property
    def is_trial_expired(self):
        if self.status == self.STATUS_TRIAL and self.trial_end:
            return timezone.now() > self.trial_end
        return False

    @property
    def days_left(self):
        if self.status == self.STATUS_TRIAL and self.trial_end:
            delta = self.trial_end - timezone.now()
            return max(0, delta.days)
        return None

    def sync_status(self):
        """Auto-expire trial if past trial_end."""
        if self.status == self.STATUS_TRIAL and self.is_trial_expired:
            self.status = self.STATUS_EXPIRED
            self.save(update_fields=['status', 'updated_at'])
