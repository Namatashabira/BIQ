from django.db import models
from students.models import Student


class AIReportComment(models.Model):
    """Stores AI-generated comments for student report cards."""

    report_snapshot_id = models.IntegerField(
        null=True, blank=True,
        help_text='ID of the GeneratedReport this comment belongs to'
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='ai_comments'
    )
    term = models.CharField(max_length=20)
    academic_year = models.CharField(max_length=20)

    # The generated comment
    comment = models.TextField()

    # Metadata
    overall_score = models.FloatField(null=True, blank=True)
    generated_by_ai = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'term', 'academic_year')
        ordering = ['-created_at']

    def __str__(self):
        return f"AI Comment - {self.student.admission_number} {self.term} {self.academic_year}"
