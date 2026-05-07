from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from decimal import Decimal
from django.utils import timezone
import secrets

# Import shared role constants from accounts
from accounts.models import ROLE_SUPERADMIN, ROLE_TENANT_ADMIN, ROLE_WORKER

# Import business configuration models
from .business_config import BusinessConfig, FeatureToggle, Terminology

User = get_user_model()

class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
        ("delivered", "Delivered"),
    ]
    
    ORDER_TYPE_CHOICES = [
        ("retail", "Retail"),
        ("wholesale", "Wholesale"),
    ]
    
    ORDER_SOURCE_CHOICES = [
        ("user", "User Order"),
        ("manual", "Manual Order"),
    ]

    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, null=True, blank=True, related_name='orders', db_index=True)
    customer_name = models.CharField(max_length=100)
    customer_email = models.EmailField()
    phone_number = models.CharField(max_length=20, default="")
    location = models.CharField(max_length=200, default="")
    order_type = models.CharField(max_length=10, choices=ORDER_TYPE_CHOICES, default="retail")
    order_source = models.CharField(max_length=10, choices=ORDER_SOURCE_CHOICES, default="user")
    delivery = models.BooleanField(default=False)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_orders')

    def __str__(self):
        return f"Order #{self.id} for {self.customer_name}"

    def calculate_total(self):
        """Calculate total from order items"""
        return sum(item.price * item.quantity for item in self.items.all())

    def save(self, *args, **kwargs):
        # Update total from items if already existing
        if self.pk:
            self.total = self.calculate_total()
        super().save(*args, **kwargs)

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product_name = models.CharField(max_length=100)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product_name} (x{self.quantity})"

    class Meta:
        ordering = ['id']


class PasswordResetToken(models.Model):
    """Model to store password reset tokens with 30-second expiration"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reset_tokens')
    token = models.CharField(max_length=100, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Reset token for {self.user.email} - {'Used' if self.used else 'Active'}"

    def save(self, *args, **kwargs):
        if not self.pk:
            # Set expiration to 30 seconds from now
            self.expires_at = timezone.now() + timezone.timedelta(seconds=30)
        super().save(*args, **kwargs)

    def is_valid(self):
        """Check if token is still valid"""
        return not self.used and timezone.now() < self.expires_at

    def time_left(self):
        """Get remaining time in seconds"""
        if self.is_valid():
            delta = self.expires_at - timezone.now()
            return max(0, int(delta.total_seconds()))
        return 0

    @classmethod
    def generate_token(cls):
        """Generate a secure random token"""
        return secrets.token_urlsafe(32)

    @classmethod
    def create_for_user(cls, user, ip_address=None):
        """Create a new reset token for user and invalidate old ones"""
        # Invalidate all existing tokens for this user
        cls.objects.filter(user=user, used=False).update(used=True)
        
        # Create new token
        token = cls(
            user=user,
            token=cls.generate_token(),
            ip_address=ip_address
        )
        token.save()
        return token


class BusinessSettings(models.Model):
    """Model to store business information for receipts and invoices"""
    tenant = models.OneToOneField('tenants.Tenant', on_delete=models.CASCADE, related_name='business_settings', null=True, blank=True)
    business_name = models.CharField(max_length=200)
    business_type = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    location = models.CharField(max_length=300)
    district = models.CharField(max_length=100)
    town = models.CharField(max_length=100)
    po_box = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Uganda')
    tax_id = models.CharField(max_length=100, blank=True)
    registration_number = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    motto = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Business Setting'
        verbose_name_plural = 'Business Settings'

    def __str__(self):
        return f"{self.business_name} ({self.tenant.name if self.tenant else 'No Tenant'})"

    @classmethod
    def get_settings(cls, tenant=None):
        """Get or create business settings for a specific tenant"""
        if tenant:
            settings, _ = cls.objects.get_or_create(
                tenant=tenant,
                defaults={
                    'business_name': tenant.name or 'Your Business Name',
                    'phone': '',
                    'location': '',
                    'district': '',
                    'town': ''
                }
            )
            return settings
        # Fallback for legacy code without tenant
        return cls.objects.first() or cls.objects.create(
            business_name='Your Business Name',
            phone='',
            location='',
            district='',
            town=''
        )


class Customer(models.Model):
    """Model to store customer information for debt tracking and invoicing"""
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True)
    total_debt = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True, related_name='customers', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'

    def __str__(self):
        return f"{self.name} - {self.phone}"

    @classmethod
    def get_or_create_customer(cls, name, phone, email=None, address=None):
        """Get existing customer or create new one"""
        customer, created = cls.objects.get_or_create(
            phone=phone,
            defaults={
                'name': name,
                'email': email or '',
                'address': address or ''
            }
        )
        # Update name and email if customer exists but info changed
        if not created:
            customer.name = name
            if email:
                customer.email = email
            if address:
                customer.address = address
            customer.save()
        return customer


class Receipt(models.Model):
    """Model to store receipt information for tracking and reprinting"""
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('mobilemoney', 'Mobile Money'),
        ('debt', 'Debt'),
    ]

    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, null=True, blank=True, related_name='receipts', db_index=True)
    receipt_number = models.CharField(max_length=20, unique=True, db_index=True)
    customer_name = models.CharField(max_length=200, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    mobile_money_number = models.CharField(max_length=20, blank=True)
    
    # Financial details
    sub_total = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    debt_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Additional debt info
    debt_partial_payment_method = models.CharField(max_length=20, blank=True)
    debt_partial_mobile_number = models.CharField(max_length=20, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Receipt'
        verbose_name_plural = 'Receipts'

    def __str__(self):
        return f"Receipt {self.receipt_number} - {self.customer_name or 'Walk-in'}"

    @classmethod
    def generate_receipt_number(cls):
        """Generate a unique receipt number using date + random slug."""
        import random
        import string
        from django.utils import timezone

        # Format: REC-YYYYMMDD-XXXXX (e.g., REC-20251221-A3F9K)
        date_str = timezone.now().strftime('%Y%m%d')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        receipt_number = f"REC-{date_str}-{random_str}"

        # Ensure uniqueness
        while cls.objects.filter(receipt_number=receipt_number).exists():
            random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
            receipt_number = f"REC-{date_str}-{random_str}"

        return receipt_number


class Appointment(models.Model):
    """Store scheduled activities/appointments with optional reminders."""

    STATUS_CHOICES = [
        ('upcoming', 'Upcoming'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ]

    title = models.CharField(max_length=255)
    participant = models.CharField(max_length=255, blank=True)
    location = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    is_all_day = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming')
    reminder_minutes_before = models.IntegerField(default=30)
    reminder_sent = models.BooleanField(default=False)
    recurrence = models.CharField(
        max_length=20,
        choices=[
            ('none', 'None'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
        ],
        default='none',
    )
    recurrence_until = models.DateField(null=True, blank=True)
    recurrence_count = models.IntegerField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_appointments')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_appointments')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_time']
        indexes = [
            models.Index(fields=['start_time']),
            models.Index(fields=['status']),
            models.Index(fields=['assigned_to']),
        ]

    def __str__(self):
        return f"{self.title} @ {self.start_time}"


class AppointmentAttendee(models.Model):
    """Attendees for appointments with RSVP state."""

    STATUS_CHOICES = [
        ('invited', 'Invited'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('tentative', 'Tentative'),
    ]

    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name='attendees')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='appointment_attendances')
    name = models.CharField(max_length=255, blank=True)
    email = models.EmailField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='invited')
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('appointment', 'email')
        ordering = ['id']

    def __str__(self):
        return f"{self.email} -> {self.appointment_id}"


class ReceiptItem(models.Model):
    """Model to store individual items in a receipt"""
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name='items')
    product_name = models.CharField(max_length=200)
    quantity = models.IntegerField()
    price_type = models.CharField(max_length=20)  # 'wholesale' or 'retail'
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    is_debt = models.BooleanField(default=False)  # True if item is on debt

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"


class AbandonedCart(models.Model):
    """Model to track abandoned shopping carts from both users and admin manual entry"""
    CART_SOURCE_CHOICES = [
        ('user', 'User Cart'),
        ('admin_manual', 'Admin Manual Entry'),
    ]
    
    # User information
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='abandoned_carts')
    session_id = models.CharField(max_length=100, blank=True)  # For non-logged in users
    customer_name = models.CharField(max_length=200, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    
    # Cart details
    cart_source = models.CharField(max_length=20, choices=CART_SOURCE_CHOICES, default='user')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    item_count = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    abandoned_at = models.DateTimeField(null=True, blank=True)
    
    # Additional info
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    notes = models.TextField(blank=True)  # Admin can add notes
    
    # Recovery tracking
    recovered = models.BooleanField(default=False)
    recovered_at = models.DateTimeField(null=True, blank=True)
    converted_order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='recovered_from_cart')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Abandoned Cart'
        verbose_name_plural = 'Abandoned Carts'
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['cart_source']),
            models.Index(fields=['recovered']),
        ]

    def __str__(self):
        if self.user:
            return f"Abandoned Cart by {self.user.username} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
        elif self.customer_name:
            return f"Abandoned Cart by {self.customer_name} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
        return f"Abandoned Cart #{self.id} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

    def calculate_totals(self):
        """Calculate total amount and item count from cart items"""
        items = self.items.all()
        self.total_amount = sum(item.total_price for item in items)
        self.item_count = sum(item.quantity for item in items)
        self.save()


class AbandonedCartItem(models.Model):
    """Model to store items in an abandoned cart"""
    cart = models.ForeignKey(AbandonedCart, on_delete=models.CASCADE, related_name='items')
    product_name = models.CharField(max_length=200)
    product_id = models.IntegerField(null=True, blank=True)  # Reference to actual product
    quantity = models.IntegerField()
    price_type = models.CharField(max_length=20, default='retail')  # 'wholesale' or 'retail'
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"

    def save(self, *args, **kwargs):
        # Auto-calculate total price
        self.total_price = self.unit_price * self.quantity
        super().save(*args, **kwargs)

