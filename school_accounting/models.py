import secrets
import hashlib
from django.db import models
from django.utils import timezone
from tenants.models import Tenant
from students.models import Student
from django.contrib.auth import get_user_model

User = get_user_model()

TERM_CHOICES = [('Term 1', 'Term 1'), ('Term 2', 'Term 2'), ('Term 3', 'Term 3')]


class SchoolExpenseCategory(models.Model):
    """Categories for school expenses"""
    CATEGORY_CHOICES = [
        ('salaries', 'Teacher Salaries'),
        ('utilities', 'Utilities (Water, Electricity)'),
        ('supplies', 'School Supplies'),
        ('maintenance', 'Maintenance & Repairs'),
        ('transport', 'Transport'),
        ('food', 'Food & Catering'),
        ('equipment', 'Equipment'),
        ('rent', 'Rent'),
        ('insurance', 'Insurance'),
        ('other', 'Other'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='school_expense_categories')
    name = models.CharField(max_length=100)
    category_type = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'School Expense Category'
        verbose_name_plural = 'School Expense Categories'
        unique_together = ['tenant', 'name']
    
    def __str__(self):
        return f"{self.name}"


class SchoolExpense(models.Model):
    """Track school expenses"""
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('cheque', 'Cheque'),
        ('other', 'Other'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='school_expenses')
    date = models.DateField(default=timezone.now)
    category = models.ForeignKey(SchoolExpenseCategory, on_delete=models.SET_NULL, null=True, related_name='expenses')
    description = models.CharField(max_length=300)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    payee = models.CharField(max_length=200, help_text='Who was paid')
    reference_number = models.CharField(max_length=100, blank=True)
    term = models.CharField(max_length=20, choices=TERM_CHOICES, blank=True)
    academic_year = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='school_expenses_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'School Expense'
        verbose_name_plural = 'School Expenses'
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.description} - {self.amount} ({self.date})"


class TeacherSalary(models.Model):
    """Track teacher salary payments"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('partial', 'Partial'),
        ('overdue', 'Overdue'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='teacher_salaries')
    teacher_name = models.CharField(max_length=200)
    employee_id = models.CharField(max_length=50, blank=True)
    month = models.DateField(help_text='Month for which salary is paid')
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2)
    allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Transport, housing, etc.')
    deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Tax, NSSF, etc.')
    net_salary = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_date = models.DateField(null=True, blank=True)
    payment_method = models.CharField(max_length=20, choices=SchoolExpense.PAYMENT_METHODS, default='bank_transfer')
    reference_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='teacher_salaries_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Teacher Salary'
        verbose_name_plural = 'Teacher Salaries'
        ordering = ['-month', 'teacher_name']
        unique_together = ['tenant', 'teacher_name', 'month']
    
    def save(self, *args, **kwargs):
        # Auto-calculate net salary
        self.net_salary = self.basic_salary + self.allowances - self.deductions
        # Auto-update status based on payment
        if self.amount_paid >= self.net_salary:
            self.status = 'paid'
        elif self.amount_paid > 0:
            self.status = 'partial'
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.teacher_name} - {self.month.strftime('%B %Y')}"


class SchoolIncome(models.Model):
    """Track school income (fees, donations, grants, etc.)"""
    INCOME_TYPES = [
        ('fees', 'School Fees'),
        ('donation', 'Donation'),
        ('grant', 'Government Grant'),
        ('fundraising', 'Fundraising'),
        ('other', 'Other Income'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='school_income')
    date = models.DateField(default=timezone.now)
    income_type = models.CharField(max_length=20, choices=INCOME_TYPES)
    description = models.CharField(max_length=300)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    source = models.CharField(max_length=200, help_text='Who paid/donated')
    payment_method = models.CharField(max_length=20, choices=SchoolExpense.PAYMENT_METHODS, default='cash')
    reference_number = models.CharField(max_length=100, blank=True)
    term = models.CharField(max_length=20, choices=TERM_CHOICES, blank=True)
    academic_year = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='school_income_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'School Income'
        verbose_name_plural = 'School Income'
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.description} - {self.amount} ({self.date})"


class SchoolDebt(models.Model):
    """Track school debts and liabilities"""
    DEBT_TYPES = [
        ('supplier', 'Supplier Debt'),
        ('loan', 'Bank Loan'),
        ('salary', 'Unpaid Salaries'),
        ('utility', 'Utility Bills'),
        ('rent', 'Rent Arrears'),
        ('other', 'Other Debt'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('overdue', 'Overdue'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='school_debts')
    creditor_name = models.CharField(max_length=200, help_text='Who we owe')
    debt_type = models.CharField(max_length=20, choices=DEBT_TYPES)
    original_amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    incurred_date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)
    description = models.TextField()
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='school_debts_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'School Debt'
        verbose_name_plural = 'School Debts'
        ordering = ['-incurred_date']
    
    def save(self, *args, **kwargs):
        # Auto-calculate balance
        self.balance = self.original_amount - self.amount_paid
        # Auto-update status
        if self.balance <= 0:
            self.status = 'paid'
        elif self.amount_paid > 0:
            self.status = 'partial'
        elif self.due_date and self.due_date < timezone.now().date():
            self.status = 'overdue'
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.creditor_name} - {self.balance} remaining"


class SchoolAsset(models.Model):
    """Track school assets"""
    ASSET_TYPES = [
        ('building', 'Building'),
        ('land', 'Land'),
        ('furniture', 'Furniture'),
        ('equipment', 'Equipment'),
        ('vehicle', 'Vehicle'),
        ('computer', 'Computer/IT Equipment'),
        ('other', 'Other Asset'),
    ]
    
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='school_assets')
    name = models.CharField(max_length=200)
    asset_type = models.CharField(max_length=20, choices=ASSET_TYPES)
    purchase_value = models.DecimalField(max_digits=12, decimal_places=2)
    current_value = models.DecimalField(max_digits=12, decimal_places=2)
    purchase_date = models.DateField()
    depreciation_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text='Annual depreciation %')
    condition = models.CharField(max_length=50, blank=True, help_text='Good, Fair, Poor')
    location = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'School Asset'
        verbose_name_plural = 'School Assets'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.current_value}"


class SalaryReceipt(models.Model):
    """Generated receipt record for a teacher salary payment"""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='salary_receipts')
    salary = models.ForeignKey(TeacherSalary, on_delete=models.CASCADE, related_name='receipts')
    receipt_number = models.CharField(max_length=50, unique=True)
    # Cryptographically secure token used for public lookup — 32 hex bytes = 64 chars
    secure_token = models.CharField(max_length=64, unique=True, blank=True)
    issued_date = models.DateField(default=timezone.now)
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='salary_receipts_issued')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Salary Receipt'
        verbose_name_plural = 'Salary Receipts'
        ordering = ['-issued_date', '-created_at']

    def save(self, *args, **kwargs):
        if not self.secure_token:
            # 32 random bytes → 64-char hex string, impossible to guess
            self.secure_token = secrets.token_hex(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.receipt_number} — {self.salary.teacher_name}"
