from django.db import models
try:
    from cloudinary.models import CloudinaryField
    _cloudinary_available = True
except ImportError:
    _cloudinary_available = False

CLASS_CHOICES = [
    ('S.1', 'S.1'), ('S.2', 'S.2'), ('S.3', 'S.3'),
    ('S.4', 'S.4'), ('S.5', 'S.5'), ('S.6', 'S.6'),
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
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-generated_at']
        unique_together = ('student', 'term', 'academic_year')  # one report per student/term/year

    def __str__(self):
        return f"{self.student} — {self.term} {self.academic_year}"


class StudentMark(models.Model):
    """Stores CA + Exam marks per student per subject per term."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='marks')
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, null=True, blank=True, db_index=True)
    subject = models.CharField(max_length=100)
    competency = models.CharField(max_length=200, blank=True)
    term = models.CharField(max_length=20)          # e.g. Term 1
    academic_year = models.CharField(max_length=20) # e.g. 2024-2025
    ca_score = models.FloatField(null=True, blank=True)
    exam_score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'subject', 'term', 'academic_year')
        ordering = ['subject']

    @property
    def total(self):
        return (self.ca_score or 0) + (self.exam_score or 0)

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
