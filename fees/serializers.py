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
    category_display = serializers.SerializerMethodField()

    class Meta:
        model = FeePayment
        fields = '__all__'

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"

    def get_category_display(self, obj):
        """Returns custom_category text if category is 'other', else the readable label."""
        if obj.payment_category == 'other' and obj.custom_category:
            return obj.custom_category
        return obj.get_payment_category_display()


from .models import ReceiptSettings


class ReceiptSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReceiptSettings
        exclude = ['user']
