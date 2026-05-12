import uuid
from django.db import models
try:
    from cloudinary.models import CloudinaryField
    _cloudinary_available = True
except ImportError:
    _cloudinary_available = False

CLASS_CHOICES = [
    # Primary
    ('Baby', 'Baby Class'),
    ('Middle', 'Middle Class'),
    ('Top', 'Top Class'),
    ('P.1', 'Primary 1'),
    ('P.2', 'Primary 2'),
    ('P.3', 'Primary 3'),
    ('P.4', 'Primary 4'),
    ('P.5', 'Primary 5'),
    ('P.6', 'Primary 6'),
    ('P.7', 'Primary 7'),
    # Secondary
    ('S.1', 'Senior 1'),
    ('S.2', 'Senior 2'),
    ('S.3', 'Senior 3'),
    ('S.4', 'Senior 4'),
    ('S.5', 'Senior 5'),
    ('S.6', 'Senior 6'),
]

SCHOOL_TYPE_CHOICES = [
    ('primary', 'Primary School'),
    ('secondary', 'Secondary School'),
    ('combined', 'Combined School'),
]


class Stream(models.Model):
    """User-customisable streams, optionally scoped to a class label."""
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, null=True, blank=True, related_name='streams', db_index=True)
    name = models.CharField(max_length=50)
    class_label = models.CharField(max_length=10, choices=CLASS_CHOICES, blank=True)

    class Meta:
        unique_together = ('tenant', 'name', 'class_label')

    def __str__(self):
        return f"{self.name} ({self.class_label})" if self.class_label else self.name


class Student(models.Model):
    GENDER_CHOICES = [('male', 'Male'), ('female', 'Female'), ('other', 'Other')]

    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, null=True, blank=True, related_name='school_students', db_index=True)
    school_type = models.CharField(max_length=20, choices=SCHOOL_TYPE_CHOICES, default='secondary', blank=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    admission_number = models.CharField(max_length=30, blank=True, null=True, default=None)
    index_number = models.CharField(max_length=30, blank=True, null=True, help_text='Exam index number (S.4 / S.6 only)')
    class_assigned = models.CharField(max_length=10, choices=CLASS_CHOICES, blank=True)
    stream = models.ForeignKey(Stream, on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True)
    photo = CloudinaryField('photo', folder='student_photos', blank=True, null=True) if _cloudinary_available else models.ImageField(upload_to='student_photos/', blank=True, null=True)
    # Location Info
    district = models.CharField(max_length=100, blank=True)
    home_address = models.CharField(max_length=200, blank=True)
    # Academic Info
    enrollment_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('active', 'Active'), ('transferred', 'Transferred'),
        ('graduated', 'Graduated'), ('suspended', 'Suspended'),
    ], default='active', blank=True)
    previous_school = models.CharField(max_length=200, blank=True, null=True)
    nationality = models.CharField(max_length=100, blank=True, default='Ugandan')
    # Fees
    fees_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, choices=[
        ('paid', 'Paid'), ('partial', 'Partial'), ('not_paid', 'Not Paid'),
    ], default='not_paid', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # admission_number unique per tenant
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'admission_number'],
                condition=models.Q(admission_number__isnull=False),
                name='unique_admission_per_tenant'
            )
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Guardian(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='guardians')
    full_name = models.CharField(max_length=100)
    relationship = models.CharField(max_length=50)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return f"{self.full_name} ({self.relationship})"


class StudentHistory(models.Model):
    HISTORY_TYPE_CHOICES = [('performance', 'Performance'), ('attendance', 'Attendance'), ('note', 'Note')]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='history')
    history_type = models.CharField(max_length=20, choices=HISTORY_TYPE_CHOICES)
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.student} - {self.title}"


class GeneratedReport(models.Model):
    """Stores a generated report card snapshot per student per term."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='reports')
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, null=True, blank=True, db_index=True)
    term = models.CharField(max_length=20)
    academic_year = models.CharField(max_length=20)
    template = models.CharField(max_length=20, default='modern')
    report_data = models.JSONField()          # full data snapshot
    secure_token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-generated_at']
        unique_together = ('student', 'term', 'academic_year')  # one report per student/term/year

    def __str__(self):
        return f"{self.student} — {self.term} {self.academic_year}"


class StudentMark(models.Model):
    """Stores A1, A2, A3 marks per student per subject per term."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='marks')
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, null=True, blank=True, db_index=True)
    subject = models.CharField(max_length=100)
    competency = models.CharField(max_length=200, blank=True)
    term = models.CharField(max_length=20)          # e.g. Term 1
    academic_year = models.CharField(max_length=20) # e.g. 2024-2025
    a1_score = models.FloatField(null=True, blank=True)  # Assessment 1 (20%)
    a2_score = models.FloatField(null=True, blank=True)  # Assessment 2 (20%)
    a3_score = models.FloatField(null=True, blank=True)  # Exam (80%)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'subject', 'term', 'academic_year')
        ordering = ['subject']

    @property
    def total(self):
        """Calculate total mark: ((A1+A2)/2) * 0.2 + A3 * 0.8"""
        a1 = self.a1_score
        a2 = self.a2_score
        a3 = self.a3_score
        if a3 is None or a3 == 0:
            return 0
        if a1 is not None and a2 is not None:
            assessment_avg = (a1 + a2) / 2
        elif a1 is not None:
            assessment_avg = a1
        elif a2 is not None:
            assessment_avg = a2
        else:
            assessment_avg = 0
        return (assessment_avg * 0.2) + (a3 * 0.8)

    @property
    def grade(self):
        t = self.total
        if t >= 80: return 'A'
        if t >= 70: return 'B'
        if t >= 60: return 'C'
        if t >= 50: return 'D'
        if t >= 40: return 'E'
        return 'F'

    def __str__(self):
        return f"{self.student} - {self.subject} ({self.term} {self.academic_year})"


class Attendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent',  'Absent'),
        ('late',    'Late'),
        ('excused', 'Excused'),
    ]

    student      = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance')
    tenant       = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, null=True, blank=True, db_index=True)
    date         = models.DateField()
    term         = models.CharField(max_length=20)
    academic_year= models.CharField(max_length=20)
    status       = models.CharField(max_length=10, choices=STATUS_CHOICES, default='present')
    note         = models.CharField(max_length=255, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'date', 'term', 'academic_year')
        ordering = ['-date', 'student__last_name']

    def __str__(self):
        return f"{self.student} — {self.date} ({self.status})"
