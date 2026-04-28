from django.contrib import admin
from .models import Student, Guardian, AcademicEnrollment, Document, Fee

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('admission_number', 'first_name', 'last_name', 'institution_type', 'created_at')
    search_fields = ('admission_number', 'first_name', 'last_name', 'email')
    list_filter = ('institution_type', 'gender', 'nationality')

@admin.register(Guardian)
class GuardianAdmin(admin.ModelAdmin):
    list_display = ('student', 'full_name', 'relationship', 'phone')
    search_fields = ('full_name', 'phone', 'email')

@admin.register(AcademicEnrollment)
class AcademicEnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'academic_year', 'term_or_semester', 'enrollment_status', 'enrollment_date')
    list_filter = ('enrollment_status', 'academic_year', 'term_or_semester')

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('student', 'document_type', 'verification_status', 'uploaded_at')
    list_filter = ('verification_status', 'document_type')

@admin.register(Fee)
class FeeAdmin(admin.ModelAdmin):
    list_display = ('student', 'fee_structure', 'total_amount', 'paid_amount', 'balance', 'payment_status')
    list_filter = ('payment_status', 'payment_method')
