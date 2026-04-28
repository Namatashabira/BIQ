from django.conf import settings
from django.db import models
from django.utils import timezone
from tenants.models import Tenant
import json


class ExpenseCategory(models.Model):
    """Categories for expenses"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='expense_categories')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Expense Category'
        verbose_name_plural = 'Expense Categories'
        unique_together = ['tenant', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.tenant.name})"


class Expense(models.Model):
    """Track business expenses"""
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('check', 'Check'),
        ('other', 'Other'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='expenses')
    date = models.DateField(default=timezone.now)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL, null=True, related_name='expenses')
    vendor = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    notes = models.TextField(blank=True)
    receipt = models.FileField(upload_to='receipts/', null=True, blank=True)
    is_recurring = models.BooleanField(default=False)
    recurring_frequency = models.CharField(max_length=20, blank=True)  # monthly, quarterly, yearly
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_expenses')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_expenses')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Expense'
        verbose_name_plural = 'Expenses'
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.vendor} - {self.amount} ({self.date})"


class Payment(models.Model):
    """Track incoming and outgoing payments"""
    PAYMENT_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]
    
    PAYMENT_STATUS = [
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='payments')
    date = models.DateField(default=timezone.now)
    party_name = models.CharField(max_length=200, help_text='Payee or Payer name')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_type = models.CharField(max_length=10, choices=PAYMENT_TYPES)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    payment_method = models.CharField(max_length=20, choices=Expense.PAYMENT_METHODS, default='cash')
    reference_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    paid_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_payments')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_payments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.party_name} - {self.amount} ({self.payment_type})"


class Tax(models.Model):
    """Track tax obligations and payments"""
    TAX_TYPES = [
        ('vat', 'VAT'),
        ('income_tax', 'Income Tax'),
        ('payroll_tax', 'Payroll Tax'),
        ('sales_tax', 'Sales Tax'),
        ('property_tax', 'Property Tax'),
        ('withholding_tax', 'Withholding Tax'),
        ('excise_duty', 'Excise Duty'),
        ('import_duty', 'Import Duty'),
        ('other', 'Other'),
    ]
    
    TAX_STATUS = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('due', 'Due'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('filed', 'Filed'),
    ]
    
    TAX_CATEGORY = [
        ('direct', 'Direct Tax'),
        ('indirect', 'Indirect Tax'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='taxes')
    
    # Core tax definition fields
    name = models.CharField(max_length=200, help_text='Tax name (e.g., VAT Standard Rate)')
    code = models.CharField(max_length=50, help_text='Unique tax code (e.g., VAT-18%)', blank=True)
    tax_type = models.CharField(max_length=20, choices=TAX_TYPES)
    category = models.CharField(max_length=20, choices=TAX_CATEGORY, default='indirect')
    rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text='Tax rate in percentage')
    
    # Tax obligation fields
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=TAX_STATUS, default='due')
    
    # Period and validity
    period_start = models.DateField(help_text='Tax period start date')
    period_end = models.DateField(help_text='Tax period end date')
    effective_date = models.DateField(null=True, blank=True, help_text='Date when tax becomes effective')
    expiry_date = models.DateField(null=True, blank=True, help_text='Date when tax expires')
    
    # Application scope
    apply_to_products = models.BooleanField(default=True, help_text='Apply to products')
    apply_to_services = models.BooleanField(default=True, help_text='Apply to services')
    is_mandatory = models.BooleanField(default=True, help_text='Is this tax mandatory')
    is_compound = models.BooleanField(default=False, help_text='Is this a compound/multi-tier tax')
    
    # Additional information
    notes = models.TextField(blank=True)
    description = models.TextField(blank=True, help_text='Detailed explanation of this tax')
    payment_reference = models.CharField(max_length=100, blank=True)
    filing_reminder_days = models.IntegerField(default=7, help_text='Days before due date to send reminder')
    
    # Audit fields
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_taxes')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_taxes')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Tax'
        verbose_name_plural = 'Taxes'
        ordering = ['-due_date']
    
    def __str__(self):
        return f"{self.get_tax_type_display()} - {self.amount} (Due: {self.due_date})"


class Asset(models.Model):
    """Track business assets for balance sheet"""
    ASSET_TYPES = [
        ('current', 'Current Asset'),
        ('fixed', 'Fixed Asset'),
        ('intangible', 'Intangible Asset'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='assets')
    name = models.CharField(max_length=200)
    asset_type = models.CharField(max_length=20, choices=ASSET_TYPES)
    value = models.DecimalField(max_digits=12, decimal_places=2)
    purchase_date = models.DateField(null=True, blank=True)
    depreciation_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text='Annual depreciation rate (%)')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Asset'
        verbose_name_plural = 'Assets'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.value}"


class Liability(models.Model):
    """Track business liabilities for balance sheet"""
    LIABILITY_TYPES = [
        ('current', 'Current Liability'),
        ('long_term', 'Long-term Liability'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='liabilities')
    name = models.CharField(max_length=200)
    liability_type = models.CharField(max_length=20, choices=LIABILITY_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Liability'
        verbose_name_plural = 'Liabilities'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.amount}"


class Equity(models.Model):
    """Track owner's equity for balance sheet"""
    EQUITY_TYPES = [
        ('capital', 'Owner Capital'),
        ('retained_earnings', 'Retained Earnings'),
        ('draws', 'Owner Draws'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='equity')
    equity_type = models.CharField(max_length=20, choices=EQUITY_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Equity'
        verbose_name_plural = 'Equity'
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.get_equity_type_display()} - {self.amount}"


class AuditLog(models.Model):
    """Track all actions on accounting records for security and compliance"""
    ACTION_TYPES = [
        ('view', 'View'),
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('export', 'Export'),
        ('print', 'Print'),
    ]
    
    MODEL_TYPES = [
        ('expense', 'Expense'),
        ('payment', 'Payment'),
        ('tax', 'Tax'),
        ('asset', 'Asset'),
        ('liability', 'Liability'),
        ('equity', 'Equity'),
        ('expense_category', 'Expense Category'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='accounting_audit_logs')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='accounting_audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    model_type = models.CharField(max_length=30, choices=MODEL_TYPES)
    object_id = models.IntegerField(help_text='ID of the record affected')
    object_repr = models.CharField(max_length=500, help_text='String representation of the object')
    
    # Detailed tracking
    changes = models.JSONField(null=True, blank=True, help_text='JSON of changes made (before/after)')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, help_text='Browser/client information')
    
    # Context
    endpoint = models.CharField(max_length=200, blank=True, help_text='API endpoint accessed')
    method = models.CharField(max_length=10, blank=True, help_text='HTTP method (GET, POST, PUT, DELETE)')
    
    # Risk indicators
    is_suspicious = models.BooleanField(default=False, help_text='Flagged for unusual activity')
    notes = models.TextField(blank=True, help_text='Additional context or flags')
    
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'tenant']),
            models.Index(fields=['user', 'action']),
            models.Index(fields=['model_type', 'object_id']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.action} {self.model_type} #{self.object_id} at {self.timestamp}"
