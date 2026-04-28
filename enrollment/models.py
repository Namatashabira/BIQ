from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()

INSTITUTION_TYPE_CHOICES = [
    ("primary", "Primary School"),
    ("secondary", "Secondary School"),
    ("university", "University"),
]
GENDER_CHOICES = [
    ("male", "Male"),
    ("female", "Female"),
    ("other", "Other"),
]
ENROLLMENT_STATUS_CHOICES = [
    ("applied", "Applied"),
    ("reviewed", "Reviewed"),
    ("approved", "Approved"),
    ("enrolled", "Enrolled"),
    ("rejected", "Rejected"),
    ("withdrawn", "Withdrawn"),
]
PAYMENT_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("partial", "Partial"),
    ("paid", "Paid"),
]
PAYMENT_METHOD_CHOICES = [
    ("mobile_money", "Mobile Money"),
    ("bank", "Bank Transfer"),
    ("card", "Card Payment"),
]

class Student(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admission_number = models.CharField(max_length=20, unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, blank=True, null=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    nationality = models.CharField(max_length=50)
    student_photo = models.ImageField(upload_to="student_photos/", blank=True, null=True)
    special_needs = models.TextField(blank=True, null=True)
    institution_type = models.CharField(max_length=20, choices=INSTITUTION_TYPE_CHOICES)
    email = models.EmailField(blank=True, null=True)  # Required for university
    study_mode = models.CharField(max_length=20, blank=True, null=True)  # full-time/part-time for university
    created_at = models.DateTimeField(auto_now_add=True)

class Guardian(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="guardians")
    full_name = models.CharField(max_length=100)
    relationship = models.CharField(max_length=50)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField()
    emergency_contact = models.CharField(max_length=100)

class AcademicEnrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="enrollments")
    academic_year = models.CharField(max_length=20)
    term_or_semester = models.CharField(max_length=20)
    grade_or_class = models.CharField(max_length=20, blank=True, null=True)  # Primary/Secondary
    stream = models.CharField(max_length=20, blank=True, null=True)  # Primary/Secondary
    subject_combination = models.CharField(max_length=100, blank=True, null=True)  # Secondary
    program = models.CharField(max_length=100, blank=True, null=True)  # University
    department = models.CharField(max_length=100, blank=True, null=True)  # University
    faculty = models.CharField(max_length=100, blank=True, null=True)  # University
    enrollment_status = models.CharField(max_length=20, choices=ENROLLMENT_STATUS_CHOICES)
    enrollment_date = models.DateField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_enrollments")
    waitlisted = models.BooleanField(default=False)
    audit_trail = models.TextField(blank=True, null=True)

class Document(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=50)
    file = models.FileField(upload_to="student_documents/")
    verification_status = models.CharField(max_length=20, default="pending")
    uploaded_at = models.DateTimeField(auto_now_add=True)

class Fee(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="fees")
    fee_structure = models.CharField(max_length=100)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True)
    invoice_file = models.FileField(upload_to="invoices/", blank=True, null=True)
    receipt_file = models.FileField(upload_to="receipts/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

# Add clear comments and production-ready structure for adaptive logic in serializers/views.