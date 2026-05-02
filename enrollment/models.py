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


# ============================================================================
# COMPETENCE-BASED CURRICULUM (CBC) MODELS FOR STUDENT REPORTING
# Uganda's New Curriculum Structure
# ============================================================================

class Subject(models.Model):
    """
    Represents a subject (course) taught to students.
    Multi-tenant: Each school has its own subjects.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='subjects',
        help_text='School/Institution (Tenant) that owns this subject'
    )
    code = models.CharField(max_length=20, help_text='Subject code (e.g., MATH01, ENG01)')
    name = models.CharField(max_length=100, help_text='Subject name (e.g., Mathematics, English)')
    description = models.TextField(blank=True, null=True)
    class_or_grade = models.CharField(
        max_length=20,
        help_text='Class/Grade (e.g., Primary 5, Form 2, Year 10)'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tenant', 'code', 'class_or_grade')
        ordering = ['name']
        verbose_name_plural = 'Subjects'
        indexes = [models.Index(fields=['tenant', 'is_active'])]

    def __str__(self):
        return f"{self.code} - {self.name} ({self.class_or_grade})"


class Competency(models.Model):
    """
    Represents competencies within a subject (CBC Framework).
    Competencies are skills/knowledge areas that students must master.
    """
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='competencies',
        help_text='Subject this competency belongs to'
    )
    code = models.CharField(max_length=20, help_text='Competency code (e.g., COMP01)')
    name = models.CharField(max_length=200, help_text='Competency name/description')
    description = models.TextField(blank=True, null=True)
    weighting = models.FloatField(
        default=1.0,
        help_text='Weight/importance of this competency (for weighted calculations)'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('subject', 'code')
        ordering = ['code']
        verbose_name_plural = 'Competencies'

    def __str__(self):
        return f"{self.code} - {self.name} ({self.subject.code})"


class Assessment(models.Model):
    """
    Stores assessment scores (Continuous Assessment + Exam scores).
    Scores can be linked to specific competencies or aggregated per subject.
    """
    ASSESSMENT_TYPE_CHOICES = [
        ('ca', 'Continuous Assessment (CA)'),
        ('exam', 'Exam'),
        ('practical', 'Practical'),
        ('project', 'Project'),
        ('participation', 'Participation'),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='assessments',
        help_text='Student being assessed'
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='assessments',
        help_text='Subject being assessed'
    )
    competency = models.ForeignKey(
        Competency,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assessments',
        help_text='Specific competency assessed (optional, can be null for overall subject scores)'
    )
    
    assessment_type = models.CharField(
        max_length=20,
        choices=ASSESSMENT_TYPE_CHOICES,
        default='ca',
        help_text='Type of assessment'
    )
    score = models.FloatField(help_text='Assessment score (0-100)')
    out_of = models.FloatField(default=100, help_text='Total marks for this assessment')
    term = models.CharField(
        max_length=20,
        help_text='Term/Semester (e.g., Term 1, Semester 1, Q1)'
    )
    academic_year = models.CharField(
        max_length=20,
        help_text='Academic year (e.g., 2024, 2024-2025)'
    )
    
    date_assessed = models.DateField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True, help_text='Assessment notes/comments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_assessed', 'subject']
        indexes = [
            models.Index(fields=['student', 'subject', 'term']),
            models.Index(fields=['student', 'academic_year']),
        ]

    def __str__(self):
        return f"{self.student.admission_number} - {self.subject.code} ({self.assessment_type}): {self.score}/{self.out_of}"


class GradingSystem(models.Model):
    """
    Configurable grading system per tenant.
    Allows schools to define their own grading scales.
    """
    tenant = models.OneToOneField(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='grading_system',
        help_text='Tenant that owns this grading system'
    )
    
    # Default grading scale (can be overridden per institution)
    GRADE_CHOICES = [
        ('A', 'Exceptional / Distinction'),
        ('B', 'Outstanding'),
        ('C', 'Satisfactory'),
        ('D', 'Basic'),
        ('E', 'Elementary / Below Expected'),
        ('F', 'Fail'),
    ]
    
    # Grade boundaries (stored as JSON for flexibility)
    grade_boundaries = models.JSONField(
        default=dict,
        help_text='Grade boundaries mapping. Default: {A: 80, B: 70, C: 60, D: 50, E: 40, F: 0}'
    )
    
    remarks = models.JSONField(
        default=dict,
        help_text='Grade remarks. Default: {A: "Exceptional", B: "Outstanding", ...}'
    )
    
    # Performance thresholds for comments
    excellent_threshold = models.FloatField(default=80, help_text='Score threshold for "Excellent" performance')
    good_threshold = models.FloatField(default=70, help_text='Score threshold for "Good" performance')
    average_threshold = models.FloatField(default=60, help_text='Score threshold for "Average" performance')
    weak_threshold = models.FloatField(default=50, help_text='Score threshold for "Needs Improvement"')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Grading System - {self.tenant.name}"


class Report(models.Model):
    """
    Student report card - generated per term/semester.
    Aggregates assessment data into a formal report.
    """
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='reports',
        help_text='Student whose report this is'
    )
    term = models.CharField(max_length=20, help_text='Term/Semester (e.g., Term 1)')
    academic_year = models.CharField(max_length=20, help_text='Academic year')
    
    # Overall performance data (JSON for flexibility)
    overall_score = models.FloatField(help_text='Overall average score')
    overall_grade = models.CharField(max_length=2, choices=GradingSystem.GRADE_CHOICES)
    overall_remark = models.CharField(max_length=100)
    
    # Subject performance (stored as JSON)
    subject_performance = models.JSONField(
        default=dict,
        help_text='Aggregated scores/grades per subject: {subject_code: {score, grade, remark, competencies: []}}'
    )
    
    # Teacher comments
    teacher_comment = models.TextField(blank=True, null=True, help_text='Auto-generated or manual teacher comment')
    
    # Report metadata
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_reports',
        help_text='User who generated this report'
    )
    
    class Meta:
        unique_together = ('student', 'term', 'academic_year')
        ordering = ['-academic_year', '-term']
        indexes = [models.Index(fields=['student', 'academic_year', 'term'])]

    def __str__(self):
        return f"{self.student.admission_number} - {self.term} {self.academic_year} ({self.overall_grade})"


# Add clear comments and production-ready structure for adaptive logic in serializers/views.