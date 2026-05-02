from django.db import models
from students.models import Student

TERM_CHOICES = [('Term 1', 'Term 1'), ('Term 2', 'Term 2'), ('Term 3', 'Term 3')]
CLASS_CHOICES = [('S.1','S.1'),('S.2','S.2'),('S.3','S.3'),('S.4','S.4'),('S.5','S.5'),('S.6','S.6')]
PAYMENT_METHOD_CHOICES = [('cash','Cash'),('bank','Bank'),('mobile_money','Mobile Money'),('other','Other')]


class FeeStructure(models.Model):
    """Defines how much each class owes per term/year."""
    class_assigned = models.CharField(max_length=10, choices=CLASS_CHOICES)
    term = models.CharField(max_length=20, choices=TERM_CHOICES)
    academic_year = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('class_assigned', 'term', 'academic_year')
        ordering = ['academic_year', 'term', 'class_assigned']

    def __str__(self):
        return f"{self.class_assigned} — {self.term} {self.academic_year}: UGX {self.amount}"


class FeePayment(models.Model):
    """Records a single fee payment made by/for a student."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fee_payments')
    term = models.CharField(max_length=20, choices=TERM_CHOICES)
    academic_year = models.CharField(max_length=20)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.student} — {self.term} {self.academic_year}: UGX {self.amount_paid}"
