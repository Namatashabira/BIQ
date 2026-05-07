from rest_framework import serializers
from .models import FeeStructure, FeeItem, FeePayment, FeeItemPayment


class FeeItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeItem
        fields = '__all__'


class FeeStructureSerializer(serializers.ModelSerializer):
    items = FeeItemSerializer(many=True, read_only=True)

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
        read_only_fields = ['receipt_number']

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"

    def get_category_display(self, obj):
        if obj.payment_category == 'other' and obj.custom_category:
            return obj.custom_category
        return obj.get_payment_category_display()


class FeeItemPaymentSerializer(serializers.ModelSerializer):
    item_name   = serializers.CharField(source='item.name', read_only=True)
    item_amount = serializers.DecimalField(source='item.amount', max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = FeeItemPayment
        fields = '__all__'


from .models import ReceiptSettings


class ReceiptSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReceiptSettings
        exclude = ['user']
        read_only_fields = ['updated_at']
