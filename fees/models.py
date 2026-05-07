import hmac
import hashlib
import secrets
from django.db import models
from django.conf import settings
from students.models import Student
from django.contrib.auth import get_user_model

User = get_user_model()

TERM_CHOICES = [('Term 1', 'Term 1'), ('Term 2', 'Term 2'), ('Term 3', 'Term 3')]
CLASS_CHOICES = [('S.1','S.1'),('S.2','S.2'),('S.3','S.3'),('S.4','S.4'),('S.5','S.5'),('S.6','S.6')]
PAYMENT_METHOD_CHOICES = [('cash','Cash'),('bank','Bank'),('mobile_money','Mobile Money'),('other','Other')]

PAYMENT_CATEGORY_CHOICES = [
    ('school_fees', 'School Fees'),
    ('uneb_registration', 'UNEB Registration'),
    ('ple_registration', 'PLE Registration'),
    ('transport', 'Transport'),
    ('meals', 'Meals / Boarding'),
    ('uniform', 'Uniform'),
    ('books', 'Books & Stationery'),
    ('medical', 'Medical'),
    ('sports', 'Sports & Activities'),
    ('other', 'Other'),
]


class FeeStructure(models.Model):
    """Defines how much each class owes per term/year."""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, null=True, blank=True, related_name='fee_structures', db_index=True)
    class_assigned = models.CharField(max_length=10, choices=CLASS_CHOICES)
    term = models.CharField(max_length=20, choices=TERM_CHOICES)
    academic_year = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tenant', 'class_assigned', 'term', 'academic_year')
        ordering = ['academic_year', 'term', 'class_assigned']

    def __str__(self):
        return f"{self.class_assigned} — {self.term} {self.academic_year}: UGX {self.amount}"


class FeeItem(models.Model):
    """A named payment item within a fee structure (e.g. Uniform, Books)."""
    structure = models.ForeignKey(FeeStructure, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=100)          # e.g. "Uniform", "Books & Stationery"
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_optional = models.BooleanField(default=False)  # optional items don't count toward required total

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} — UGX {self.amount}"


def _generate_receipt_number():
    """HMAC-signed receipt number: RCP-<date>-<random>-<hmac_check>"""
    from datetime import date
    rand = secrets.token_hex(4).upper()          # 8 hex chars
    date_part = date.today().strftime('%Y%m%d')
    payload = f"{date_part}-{rand}"
    secret = (settings.SECRET_KEY or 'fallback').encode()
    check = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()[:6].upper()
    return f"RCP-{date_part}-{rand}-{check}"


class FeePayment(models.Model):
    """Records a single fee payment made by/for a student."""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, null=True, blank=True, related_name='fee_payments', db_index=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fee_payments')
    term = models.CharField(max_length=20, choices=TERM_CHOICES)
    academic_year = models.CharField(max_length=20)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    reference = models.CharField(max_length=100, blank=True)
    payment_category = models.CharField(max_length=50, choices=PAYMENT_CATEGORY_CHOICES, default='school_fees')
    custom_category = models.CharField(max_length=100, blank=True, help_text='Used when payment_category is "other"')
    notes = models.TextField(blank=True)
    receipt_number = models.CharField(max_length=40, unique=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date']

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            # Ensure uniqueness (collision is astronomically unlikely but guard anyway)
            for _ in range(5):
                candidate = _generate_receipt_number()
                if not FeePayment.objects.filter(receipt_number=candidate).exists():
                    self.receipt_number = candidate
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} — {self.term} {self.academic_year}: UGX {self.amount_paid}"


class FeeItemPayment(models.Model):
    """Tracks whether a student has paid a specific FeeItem."""
    tenant   = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, null=True, blank=True, db_index=True)
    student  = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='item_payments')
    item     = models.ForeignKey(FeeItem, on_delete=models.CASCADE, related_name='student_payments')
    payment  = models.ForeignKey(FeePayment, on_delete=models.SET_NULL, null=True, blank=True, related_name='item_payments')
    paid_at  = models.DateField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'item')  # one record per student per item

    def __str__(self):
        return f"{self.student} paid {self.item}"


class ReceiptSettings(models.Model):
    """Stores school logo, bursar signature and stamp settings per tenant."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='receipt_settings')
    # School logo
    logo = models.TextField(blank=True)   # base64 data URL or Cloudinary URL
    # Bursar signature
    sig_mode = models.CharField(max_length=10, default='', blank=True)  # 'image' | 'name' | ''
    sig_image = models.TextField(blank=True)   # base64 data URL
    sig_name  = models.CharField(max_length=200, blank=True)
    sig_label = models.CharField(max_length=100, default='Bursar', blank=True)
    # School stamp
    stamp_raw = models.TextField(blank=True)   # base64 data URL of original stamp (no date)
    stamp_offset_x  = models.IntegerField(default=0)
    stamp_offset_y  = models.IntegerField(default=0)
    stamp_rotate    = models.IntegerField(default=0)
    stamp_circular  = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ReceiptSettings for {self.user}"
