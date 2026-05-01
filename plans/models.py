import uuid
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


class PaymentRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='payment_requests')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='payment_requests')
    sender_name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=30)
    payment_method = models.CharField(max_length=20)  # mtn, airtel, bank
    transaction_id = models.CharField(max_length=200)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    activation_code = models.CharField(max_length=20, blank=True)
    code_expires_at = models.DateTimeField(null=True, blank=True)
    code_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    admin_note = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.tenant.name} — {self.plan.name} — {self.status}"

    def generate_code(self):
        """Generate a unique 10-char uppercase activation code, expires in 24h."""
        code = uuid.uuid4().hex[:10].upper()
        self.activation_code = code
        self.status = self.STATUS_APPROVED
        self.code_expires_at = timezone.now() + timedelta(hours=24)
        self.save(update_fields=['activation_code', 'status', 'code_expires_at', 'updated_at'])
        return code

