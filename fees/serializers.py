from rest_framework import serializers
from .models import FeeStructure, FeePayment


class FeeStructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeStructure
        fields = '__all__'


class FeePaymentSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    student_class = serializers.CharField(source='student.class_assigned', read_only=True)
    admission_number = serializers.CharField(source='student.admission_number', read_only=True)

    class Meta:
        model = FeePayment
        fields = '__all__'

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"
