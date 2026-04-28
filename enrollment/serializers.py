from rest_framework import serializers
from .models import Student, Guardian, AcademicEnrollment, Document, Fee

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
