from rest_framework import serializers
from .models import (
    Student, Guardian, AcademicEnrollment, Document, Fee,
    Subject, Competency, Assessment, GradingSystem, Report
)

class GuardianSerializer(serializers.ModelSerializer):
    class Meta:
        model = Guardian
        fields = '__all__'

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = '__all__'

class FeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fee
        fields = '__all__'

class AcademicEnrollmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicEnrollment
        fields = '__all__'

class StudentSerializer(serializers.ModelSerializer):
    guardians = GuardianSerializer(many=True, required=False)
    documents = DocumentSerializer(many=True, required=False)
    enrollments = AcademicEnrollmentSerializer(many=True, required=False)
    fees = FeeSerializer(many=True, required=False)

    class Meta:
        model = Student
        fields = '__all__'

    def validate(self, data):
        institution_type = data.get('institution_type')
        # Adaptive validation logic
        if institution_type == 'university':
            if not data.get('email'):
                raise serializers.ValidationError({'email': 'Email is required for university students.'})
            if not data.get('study_mode'):
                raise serializers.ValidationError({'study_mode': 'Study mode is required for university students.'})
        return data

    def create(self, validated_data):
        guardians_data = validated_data.pop('guardians', [])
        documents_data = validated_data.pop('documents', [])
        enrollments_data = validated_data.pop('enrollments', [])
        fees_data = validated_data.pop('fees', [])
        student = Student.objects.create(**validated_data)
        for guardian_data in guardians_data:
            Guardian.objects.create(student=student, **guardian_data)
        for document_data in documents_data:
            Document.objects.create(student=student, **document_data)
        for enrollment_data in enrollments_data:
            AcademicEnrollment.objects.create(student=student, **enrollment_data)
        for fee_data in fees_data:
            Fee.objects.create(student=student, **fee_data)
        return student

    def update(self, instance, validated_data):
        # Update logic for nested objects can be added here
        return super().update(instance, validated_data)


# ============================================================================
# COMPETENCE-BASED CURRICULUM (CBC) SERIALIZERS
# ============================================================================

class SubjectSerializer(serializers.ModelSerializer):
    """Serializer for Subject model"""
    competency_count = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = ['id', 'tenant', 'code', 'name', 'description', 'class_or_grade', 'is_active', 'competency_count', 'created_at']
        read_only_fields = ['created_at', 'competency_count']

    def get_competency_count(self, obj):
        return obj.competencies.filter(is_active=True).count()


class CompetencySerializer(serializers.ModelSerializer):
    """Serializer for Competency model"""
    subject_name = serializers.CharField(source='subject.name', read_only=True)

    class Meta:
        model = Competency
        fields = ['id', 'subject', 'subject_name', 'code', 'name', 'description', 'weighting', 'is_active', 'created_at']
        read_only_fields = ['created_at', 'subject_name']


class AssessmentSerializer(serializers.ModelSerializer):
    """Serializer for Assessment model"""
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    competency_code = serializers.CharField(source='competency.code', read_only=True, allow_null=True)
    competency_name = serializers.CharField(source='competency.name', read_only=True, allow_null=True)
    percentage = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = [
            'id', 'student', 'subject', 'subject_code', 'subject_name',
            'competency', 'competency_code', 'competency_name',
            'assessment_type', 'score', 'out_of', 'percentage',
            'term', 'academic_year', 'date_assessed', 'notes', 'created_at'
        ]
        read_only_fields = ['created_at', 'subject_code', 'subject_name', 'competency_code', 'competency_name', 'percentage']

    def get_percentage(self, obj):
        """Calculate percentage from score and out_of"""
        return round((obj.score / obj.out_of) * 100, 2) if obj.out_of > 0 else 0


class GradingSystemSerializer(serializers.ModelSerializer):
    """Serializer for GradingSystem model"""
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)

    class Meta:
        model = GradingSystem
        fields = [
            'id', 'tenant', 'tenant_name',
            'grade_boundaries', 'remarks',
            'excellent_threshold', 'good_threshold', 'average_threshold', 'weak_threshold',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'tenant_name']


class CompetencyPerformanceSerializer(serializers.Serializer):
    """Serializer for competency performance data (nested in report)"""
    competency_code = serializers.CharField()
    competency_name = serializers.CharField()
    score = serializers.FloatField()
    grade = serializers.CharField()
    remark = serializers.CharField()


class SubjectPerformanceSerializer(serializers.Serializer):
    """Serializer for subject performance data (nested in report)"""
    subject_code = serializers.CharField()
    subject_name = serializers.CharField()
    score = serializers.FloatField()
    grade = serializers.CharField()
    remark = serializers.CharField()
    competencies = CompetencyPerformanceSerializer(many=True)


class ReportSerializer(serializers.ModelSerializer):
    """Serializer for Report model"""
    student_name = serializers.SerializerMethodField()
    student_admission_number = serializers.CharField(source='student.admission_number', read_only=True)
    generated_by_name = serializers.CharField(source='generated_by.get_full_name', read_only=True, allow_null=True)
    subject_performance = SubjectPerformanceSerializer(read_only=True)

    class Meta:
        model = Report
        fields = [
            'id', 'student', 'student_name', 'student_admission_number',
            'term', 'academic_year',
            'overall_score', 'overall_grade', 'overall_remark',
            'subject_performance', 'teacher_comment',
            'generated_by', 'generated_by_name', 'generated_at'
        ]
        read_only_fields = ['id', 'generated_at', 'student_name', 'student_admission_number', 'generated_by_name']

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"
