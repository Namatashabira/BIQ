# core/business_config.py
"""
Business Configuration Models
Provides tenant-specific configuration for feature toggles, terminology, and business presets.
"""
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
from tenants.models import Tenant

# Shared defaults for pricing settings so frontend and backend stay in sync
PRICING_DEFAULTS = {
    'default_currency': 'USD',
    'country': 'UG',
    'wholesale_threshold': 10,
    'price_priority': 'retail-first',
    'wholesale_availability': ['everyone'],
    'enable_tax': False,
    'tax_mode': 'included',
    'price_missing': 'default',
    'rounding': 'nearest',
    'order_limit_min': 1,
    'order_limit_max': 99999,
}

# Central place for all feature flags and their default enabled state
FEATURE_DEFAULTS = {
    'dashboard_enabled': True,
    'organizations_enabled': True,
    'product_enabled': True,
    'inventory_enabled': True,
    'orders_enabled': True,
    'customers_enabled': True,
    'scheduling_enabled': True,
    'manual_entry_enabled': True,
    'payments_enabled': True,
    'partial_payments_enabled': False,
    'approval_required': False,
    'delivery_enabled': False,
    'batch_tracking': False,
    'expiry_tracking': False,
    'analytics_enabled': True,
    'ai_insights_enabled': True,
    'accounting_enabled': True,
    'enrollment_enabled': True,
}


def _default_allowed_pages():
    # Use feature keys as a baseline for page identifiers
    return list(FEATURE_DEFAULTS.keys())


class BusinessConfig(models.Model):
    """
    Main business configuration for each tenant.
    Stores business type (used only as preset), industry metadata, and onboarding status.
    """
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
    
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='business_config'
    )
    
    # Business type is ONLY used for applying presets, NOT for logic
    business_type = models.CharField(
        max_length=50,
        choices=BUSINESS_TYPE_CHOICES,
        default='other',
        help_text='Used only for applying initial presets. Does NOT control app behavior.'
    )
    
    # Metadata
    industry_description = models.TextField(blank=True)
    onboarding_completed = models.BooleanField(default=False)
    preset_applied = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Business Configuration'
        verbose_name_plural = 'Business Configurations'
        
    def __str__(self):
        return f"{self.tenant.name} - {self.get_business_type_display()}"
    
    def apply_business_preset(self):
        """
        Apply default feature toggles and terminology based on business type.
        This is called ONCE during onboarding.
        """
        if self.preset_applied:
            return
        
        preset = BUSINESS_PRESETS.get(self.business_type)
        if not preset:
            preset = BUSINESS_PRESETS['other']
        
        # Apply feature toggles (merge defaults with preset overrides)
        merged_features = {**FEATURE_DEFAULTS, **preset['features']}
        for feature_key, enabled in merged_features.items():
            FeatureToggle.objects.update_or_create(
                tenant=self.tenant,
                feature_key=feature_key,
                defaults={'enabled': enabled}
            )
        
        # Apply terminology
        for entity, label in preset['terminology'].items():
            Terminology.objects.update_or_create(
                tenant=self.tenant,
                entity=entity,
                defaults={'label': label, 'label_plural': label + 's'}
            )
        
        self.preset_applied = True
        self.save()
        
        return True


class WorkerAccessInvite(models.Model):
    """One-time password invite for workers with page-level permissions."""

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='access_invites'
    )

    name = models.CharField(max_length=150)
    email = models.EmailField()
    otp_code = models.CharField(max_length=12, db_index=True)
    otp_expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    # New invites should not grant access until explicitly assigned
    allowed_pages = models.JSONField(default=list)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_access_invites'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['tenant', 'email']
        ordering = ['-created_at']
        verbose_name = 'Worker Access Invite'
        verbose_name_plural = 'Worker Access Invites'

    def __str__(self):
        status = 'used' if self.used else 'active'
        return f"{self.email} ({status})"

    @staticmethod
    def generate_otp():
        import secrets
        import string
        # 11-character mixed code: letters, digits, and safe symbols
        symbols = '!@#$%^*?'
        alphabet = string.ascii_letters + string.digits + symbols
        return ''.join(secrets.choice(alphabet) for _ in range(11))

    def refresh_otp(self, minutes_valid=60 * 24):
        self.otp_code = self.generate_otp()
        self.otp_expires_at = timezone.now() + timezone.timedelta(minutes=minutes_valid)
        self.used = False
        return self


class WorkerPageAccess(models.Model):
    """Per-user page visibility configuration."""

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='page_access_controls'
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='page_access'
    )

    # Workers get no page access until explicitly assigned
    allowed_pages = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Worker Page Access'
        verbose_name_plural = 'Worker Page Access'

    def __str__(self):
        return f"Access for {self.user.email or self.user.username}"


class PricingSettings(models.Model):
    """Global pricing/tax settings per tenant (currency, wholesale rules, limits)."""

    PRICE_PRIORITY_CHOICES = [
        ('retail-first', 'Retail first'),
        ('wholesale-first', 'Wholesale first'),
        ('country-first', 'Country first'),
    ]

    TAX_MODE_CHOICES = [
        ('included', 'Tax included'),
        ('added', 'Tax added at checkout'),
    ]

    PRICE_MISSING_CHOICES = [
        ('default', 'Allow zero price'),
        ('block', 'Block add to cart'),
        ('hide', 'Hide product'),
    ]

    ROUNDING_CHOICES = [
        ('nearest', 'Round to nearest'),
        ('up', 'Round up'),
        ('down', 'Round down'),
    ]

    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='pricing_settings'
    )

    default_currency = models.CharField(max_length=10, default=PRICING_DEFAULTS['default_currency'])
    country = models.CharField(max_length=5, default=PRICING_DEFAULTS['country'])
    wholesale_threshold = models.IntegerField(default=PRICING_DEFAULTS['wholesale_threshold'])
    price_priority = models.CharField(max_length=32, choices=PRICE_PRIORITY_CHOICES, default=PRICING_DEFAULTS['price_priority'])
    wholesale_availability = models.JSONField(default=list, help_text='List of roles allowed: everyone, wholesalers, assigned')
    enable_tax = models.BooleanField(default=PRICING_DEFAULTS['enable_tax'])
    tax_mode = models.CharField(max_length=20, choices=TAX_MODE_CHOICES, default=PRICING_DEFAULTS['tax_mode'])
    price_missing = models.CharField(max_length=20, choices=PRICE_MISSING_CHOICES, default=PRICING_DEFAULTS['price_missing'])
    rounding = models.CharField(max_length=20, choices=ROUNDING_CHOICES, default=PRICING_DEFAULTS['rounding'])
    order_limit_min = models.IntegerField(default=PRICING_DEFAULTS['order_limit_min'])
    order_limit_max = models.IntegerField(default=PRICING_DEFAULTS['order_limit_max'])

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pricing Settings'
        verbose_name_plural = 'Pricing Settings'

    def __str__(self):
        return f"{self.tenant.name} Pricing"

    @classmethod
    def default_values(cls):
        """Provide defaults matching the frontend helpers."""
        return {**PRICING_DEFAULTS, 'wholesale_availability': list(PRICING_DEFAULTS['wholesale_availability'])}


class FeatureToggle(models.Model):
    """
    Feature flags that control which features are enabled for a tenant.
    Pages, sections, and functionality appear/disappear based on these flags.
    """
    FEATURE_CHOICES = [
        ('dashboard_enabled', 'Dashboard'),
        ('organizations_enabled', 'My Organizations'),
        ('product_enabled', 'Products/Services'),
        ('inventory_enabled', 'Inventory Management'),
        ('orders_enabled', 'Orders/Transactions'),
        ('customers_enabled', 'Customers/Contacts'),
        ('scheduling_enabled', 'Scheduling & Appointments'),
        ('manual_entry_enabled', 'Manual Entry'),
        ('payments_enabled', 'Payments & Receipts'),
        ('partial_payments_enabled', 'Partial Payments'),
        ('approval_required', 'Approval Workflow'),
        ('delivery_enabled', 'Delivery Management'),
        ('batch_tracking', 'Batch/Lot Tracking'),
        ('expiry_tracking', 'Expiry Date Tracking'),
        ('analytics_enabled', 'Analytics'),
        ('ai_insights_enabled', 'AI Insights'),
        ('accounting_enabled', 'Accounting'),
        ('enrollment_enabled', 'Enrollment'),
        ('multi_location', 'Multi-Location Support'),
        ('customer_portal', 'Customer Portal'),
        ('supplier_management', 'Supplier Management'),
        ('loyalty_program', 'Loyalty Program'),
        ('advanced_analytics', 'Advanced Analytics'),
    ]
    
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='feature_toggles'
    )
    
    feature_key = models.CharField(
        max_length=100,
        choices=FEATURE_CHOICES,
        help_text='Feature identifier used in code'
    )
    
    enabled = models.BooleanField(
        default=False,
        help_text='Whether this feature is enabled'
    )
    
    # Optional: metadata
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['tenant', 'feature_key']
        verbose_name = 'Feature Toggle'
        verbose_name_plural = 'Feature Toggles'
        indexes = [
            models.Index(fields=['tenant', 'feature_key']),
        ]
    
    def __str__(self):
        status = "✓" if self.enabled else "✗"
        return f"{status} {self.get_feature_key_display()} ({self.tenant.name})"


class Terminology(models.Model):
    """
    Dynamic labels for UI elements.
    Maps generic internal entities to business-specific labels.
    """
    ENTITY_CHOICES = [
        ('resource', 'Resource (Product/Service/Subject)'),
        ('transaction', 'Transaction (Order/Visit/Enrollment)'),
        ('entity', 'Entity (Customer/Patient/Student)'),
        ('inventory', 'Inventory (Stock/Supplies)'),
        ('payment', 'Payment'),
        ('schedule', 'Schedule (Appointment/Session)'),
        ('location', 'Location (Branch/Facility)'),
    ]
    
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='terminology'
    )
    
    entity = models.CharField(
        max_length=50,
        choices=ENTITY_CHOICES,
        help_text='Internal generic entity name'
    )
    
    label = models.CharField(
        max_length=100,
        help_text='Business-specific singular label (e.g., "Product", "Patient")'
    )
    
    label_plural = models.CharField(
        max_length=100,
        help_text='Business-specific plural label (e.g., "Products", "Patients")'
    )
    
    # Optional: additional context
    description = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['tenant', 'entity']
        verbose_name = 'Terminology'
        verbose_name_plural = 'Terminology'
        indexes = [
            models.Index(fields=['tenant', 'entity']),
        ]
    
    def __str__(self):
        return f"{self.entity} → {self.label} ({self.tenant.name})"


# ===========================
# BUSINESS PRESETS
# ===========================
# These are applied ONCE during onboarding based on business type
# After that, everything is configurable via feature toggles and terminology

BUSINESS_PRESETS = {
    'school': {
        'features': {
            'inventory_enabled': False,
            'scheduling_enabled': True,
            'payments_enabled': True,
            'partial_payments_enabled': True,
            'approval_required': False,
            'delivery_enabled': False,
            'batch_tracking': False,
            'expiry_tracking': False,
        },
        'terminology': {
            'resource': 'Subject',
            'transaction': 'Enrollment',
            'entity': 'Student',
            'inventory': 'Supplies',
            'payment': 'Fee Payment',
            'schedule': 'Class',
        }
    },
    'supermarket': {
        'features': {
            'inventory_enabled': True,
            'scheduling_enabled': False,
            'payments_enabled': True,
            'partial_payments_enabled': True,
            'approval_required': False,
            'delivery_enabled': True,
            'batch_tracking': True,
            'expiry_tracking': True,
        },
        'terminology': {
            'resource': 'Product',
            'transaction': 'Sale',
            'entity': 'Customer',
            'inventory': 'Stock',
            'payment': 'Payment',
        }
    },
    'hardware': {
        'features': {
            'inventory_enabled': True,
            'scheduling_enabled': False,
            'payments_enabled': True,
            'partial_payments_enabled': True,
            'approval_required': False,
            'delivery_enabled': True,
            'batch_tracking': False,
            'expiry_tracking': False,
        },
        'terminology': {
            'resource': 'Product',
            'transaction': 'Sale',
            'entity': 'Customer',
            'inventory': 'Stock',
            'payment': 'Payment',
        }
    },
    'agrobusiness': {
        'features': {
            'inventory_enabled': True,
            'scheduling_enabled': True,
            'payments_enabled': True,
            'partial_payments_enabled': True,
            'approval_required': False,
            'delivery_enabled': True,
            'batch_tracking': True,
            'expiry_tracking': True,
        },
        'terminology': {
            'resource': 'Product',
            'transaction': 'Order',
            'entity': 'Customer',
            'inventory': 'Stock',
            'payment': 'Payment',
            'schedule': 'Service',
        }
    },
    'wholesale': {
        'features': {
            'inventory_enabled': True,
            'scheduling_enabled': False,
            'payments_enabled': True,
            'partial_payments_enabled': True,
            'approval_required': True,
            'delivery_enabled': True,
            'batch_tracking': True,
            'expiry_tracking': True,
        },
        'terminology': {
            'resource': 'Product',
            'transaction': 'Order',
            'entity': 'Customer',
            'inventory': 'Stock',
            'payment': 'Payment',
        }
    },
    'healthcare': {
        'features': {
            'inventory_enabled': True,
            'scheduling_enabled': True,
            'payments_enabled': True,
            'partial_payments_enabled': True,
            'approval_required': False,
            'delivery_enabled': False,
            'batch_tracking': True,
            'expiry_tracking': True,
        },
        'terminology': {
            'resource': 'Service',
            'transaction': 'Visit',
            'entity': 'Patient',
            'inventory': 'Medical Supplies',
            'payment': 'Bill Payment',
            'schedule': 'Appointment',
        }
    },

    'retail': {
        'features': {
            'inventory_enabled': True,
            'scheduling_enabled': False,
            'payments_enabled': True,
            'partial_payments_enabled': True,
            'approval_required': False,
            'delivery_enabled': True,
            'batch_tracking': False,
            'expiry_tracking': False,
        },
        'terminology': {
            'resource': 'Product',
            'transaction': 'Order',
            'entity': 'Customer',
            'inventory': 'Stock',
            'payment': 'Payment',
        }
    },
    'services': {
        'features': {
            'inventory_enabled': False,
            'scheduling_enabled': True,
            'payments_enabled': True,
            'partial_payments_enabled': True,
            'approval_required': False,
            'delivery_enabled': False,
            'batch_tracking': False,
            'expiry_tracking': False,
        },
        'terminology': {
            'resource': 'Service',
            'transaction': 'Job',
            'entity': 'Client',
            'inventory': 'Supplies',
            'payment': 'Payment',
            'schedule': 'Appointment',
        }
    },
    'other': {
        'features': {
            'inventory_enabled': True,
            'scheduling_enabled': False,
            'payments_enabled': True,
            'partial_payments_enabled': False,
            'approval_required': False,
            'delivery_enabled': False,
            'batch_tracking': False,
            'expiry_tracking': False,
        },
        'terminology': {
            'resource': 'Item',
            'transaction': 'Transaction',
            'entity': 'Contact',
            'inventory': 'Stock',
            'payment': 'Payment',
        }
    },
    'restaurant': {
        'features': {
            'inventory_enabled': True,
            'scheduling_enabled': True,
            'payments_enabled': True,
            'partial_payments_enabled': False,
            'approval_required': False,
            'delivery_enabled': True,
            'batch_tracking': True,
            'expiry_tracking': True,
        },
        'terminology': {
            'resource': 'Menu Item',
            'transaction': 'Order',
            'entity': 'Customer',
            'inventory': 'Kitchen Stock',
            'payment': 'Payment',
            'schedule': 'Reservation',
        }
    },
    'manufacturing': {
        'features': {
            'inventory_enabled': True,
            'scheduling_enabled': True,
            'payments_enabled': True,
            'partial_payments_enabled': True,
            'approval_required': True,
            'delivery_enabled': True,
            'batch_tracking': True,
            'expiry_tracking': False,
        },
        'terminology': {
            'resource': 'Product',
            'transaction': 'Production Order',
            'entity': 'Client',
            'inventory': 'Raw Materials',
            'payment': 'Payment',
            'schedule': 'Production Schedule',
        }
    },
    'transportation': {
        'features': {
            'inventory_enabled': True,
            'scheduling_enabled': True,
            'payments_enabled': True,
            'partial_payments_enabled': True,
            'approval_required': False,
            'delivery_enabled': True,
            'batch_tracking': False,
            'expiry_tracking': False,
        },
        'terminology': {
            'resource': 'Service',
            'transaction': 'Shipment',
            'entity': 'Customer',
            'inventory': 'Fleet',
            'payment': 'Payment',
            'schedule': 'Route',
        }
    },
    'ecommerce': {
        'features': {
            'inventory_enabled': True,
            'scheduling_enabled': False,
            'payments_enabled': True,
            'partial_payments_enabled': True,
            'approval_required': False,
            'delivery_enabled': True,
            'batch_tracking': True,
            'expiry_tracking': False,
        },
        'terminology': {
            'resource': 'Product',
            'transaction': 'Order',
            'entity': 'Customer',
            'inventory': 'Stock',
            'payment': 'Payment',
        }
    },
    'nonprofit': {
        'features': {
            'inventory_enabled': True,
            'scheduling_enabled': True,
            'payments_enabled': True,
            'partial_payments_enabled': True,
            'approval_required': True,
            'delivery_enabled': False,
            'batch_tracking': False,
            'expiry_tracking': False,
        },
        'terminology': {
            'resource': 'Service',
            'transaction': 'Project',
            'entity': 'Beneficiary',
            'inventory': 'Supplies',
            'payment': 'Donation',
            'schedule': 'Program',
        }
    },
}


# Predefined color palettes - lookup table
COLOR_PALETTES = {
    '#00A09D': ['#00A09D', '#F8F8F8', '#F3D2C1'],  # Palette 1
    '#6C63FF': ['#6C63FF', '#F8F8F8', '#F7C6D0'],  # Palette 2
    '#875A7B': ['#875A7B', '#F8F8F8', '#F4B6C2'],  # Palette 3
    '#A9A9F5': ['#A9A9F5', '#F8F8F8', '#B8F5C2'],  # Palette 4
    '#B0B3F8': ['#B0B3F8', '#F8F8F8', '#FFF1D6'],  # Palette 5
    '#F06050': ['#F06050', '#F8F8F8', '#FFD6B3'],  # Palette 6
    '#D97380': ['#D97380', '#F8F8F8', '#E3ECFA'],  # Palette 7
    '#E2A76F': ['#E2A76F', '#F8F8F8', '#D7D2CB'],  # Palette 8
    '#F7CD1F': ['#F7CD1F', '#F8F8F8', '#5F9C7E'],  # Palette 9
    '#5F9C7E': ['#5F9C7E', '#F8F8F8', '#E9E4DF'],  # Palette 10
    '#00C0EF': ['#00C0EF', '#F8F8F8', '#C0392B'],  # Palette 11
    '#3F51B5': ['#3F51B5', '#F8F8F8', '#A6A6A6'],  # Palette 12
    '#34495E': ['#34495E', '#F8F8F8', '#F5E1C8'],  # Palette 13
    '#1ABC9C': ['#1ABC9C', '#F8F8F8', '#2E7D5A'],  # Palette 14
    '#2C3E50': ['#2C3E50', '#F8F8F8', '#C0392B'],  # Palette 15
    '#0D9488': ['#0D9488', '#0F172A', '#F8FAFC'],  # Palette 16 - Teal / Navy / Mist White
    '#4F46E5': ['#4F46E5', '#111827', '#F9FAFB'],  # Palette 17 - Indigo / Charcoal / Light Gray
    '#10B981': ['#10B981', '#1F2937', '#F3F4F6'],  # Palette 18 - Emerald / Dark Gray / Soft White
    '#2563EB': ['#2563EB', '#1E293B', '#FFFFFF'],  # Palette 19 - Blue / Graphite / Pure White
    '#0F3D2E': ['#0F3D2E', '#1F2933', '#F8FAF9'],  # Palette 20 - Dark Green / Slate / Off-White
    '#7C3AED': ['#7C3AED', '#1F1F2E', '#FAFAFB'],  # Palette 21 - Purple / Deep Gray / Light Mist
    '#F97316': ['#F97316', '#1F2937', '#FFF7ED'],  # Palette 22 - Orange / Charcoal / Soft White
    '#E11D48': ['#E11D48', '#334155', '#FFFFFF'],  # Palette 23 - Rose / Slate / Snow White
    '#06B6D4': ['#06B6D4', '#020617', '#F1F5F9'],  # Palette 24 - Cyan / Midnight / Cloud Gray
    '#111827': ['#111827', '#374151', '#F9FAFB'],  # Palette 25 - Monochrome Pro
    '#3B82F6': ['#3B82F6', '#10B981', '#8B5CF6'],  # Default
}

class Theme(models.Model):
    """
    Store tenant's brand theme including logo and color identifier.
    The color identifier is used to lookup the full color triplet from COLOR_PALETTES.
    """
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='theme'
    )
    
    # Logo
    logo = models.ImageField(upload_to='logos/', null=True, blank=True)
    
    # Color identifier - used to lookup full triplet
    color = models.CharField(
        max_length=7, 
        default='#3B82F6',
        help_text='Primary color identifier used to lookup full palette'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Theme'
        verbose_name_plural = 'Themes'
    
    def __str__(self):
        return f"{self.tenant.name} - Theme ({self.color})"
    
    def get_colors(self):
        """Return the full color triplet [primary, secondary, accent]"""
        return COLOR_PALETTES.get(self.color, COLOR_PALETTES['#3B82F6'])
    
    @property
    def primary_color(self):
        return self.get_colors()[0]
    
    @property
    def secondary_color(self):
        return self.get_colors()[1]
    
    @property
    def accent_color(self):
        return self.get_colors()[2]
