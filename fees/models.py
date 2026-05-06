from django.db import models
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.student} — {self.term} {self.academic_year}: UGX {self.amount_paid}"


class ReceiptSettings(models.Model):
    """Stores bursar signature and school stamp settings per user/tenant."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='receipt_settings')
    # Bursar signature
    sig_mode = models.CharField(max_length=10, default='', blank=True)  # 'image' | 'name' | ''
    sig_image = models.TextField(blank=True)   # base64 data URL
    sig_name  = models.CharField(max_length=200, blank=True)
    sig_label = models.CharField(max_length=100, default='Bursar', blank=True)  # e.g. 'Bursar', 'Headteacher', 'Director'
    # School stamp
    stamp_raw = models.TextField(blank=True)   # base64 data URL of original stamp (no date)
    stamp_offset_x  = models.IntegerField(default=0)
    stamp_offset_y  = models.IntegerField(default=0)
    stamp_rotate    = models.IntegerField(default=0)
    stamp_circular  = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"ReceiptSettings for {self.user}"
