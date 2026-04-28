from rest_framework import serializers
from .models import (
    ExpenseCategory, Expense, Payment, Tax,
    Asset, Liability, Equity, AuditLog
)


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ['id', 'name', 'description', 'created_at']
        read_only_fields = ['id', 'created_at']


class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    receipt_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Expense
        fields = [
            'id', 'date', 'category', 'category_name', 'vendor', 'amount',
            'payment_method', 'notes', 'receipt', 'receipt_url', 'is_recurring',
            'recurring_frequency', 'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by_name', 'receipt_url']
    
    def get_receipt_url(self, obj):
        if obj.receipt:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.receipt.url)
        return None


class PaymentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'date', 'party_name', 'amount', 'payment_type', 'status',
            'payment_method', 'reference_number', 'notes', 'due_date', 'paid_date',
            'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by_name']


class TaxSerializer(serializers.ModelSerializer):
    tax_type_display = serializers.CharField(source='get_tax_type_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = Tax
        fields = [
            'id', 'tax_type', 'tax_type_display', 'amount', 'due_date', 'paid_date',
            'status', 'period_start', 'period_end', 'notes', 'payment_reference',
            'created_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by_name']


class AssetSerializer(serializers.ModelSerializer):
    asset_type_display = serializers.CharField(source='get_asset_type_display', read_only=True)
    
    class Meta:
        model = Asset
        fields = [
            'id', 'name', 'asset_type', 'asset_type_display', 'value',
            'purchase_date', 'depreciation_rate', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class LiabilitySerializer(serializers.ModelSerializer):
    liability_type_display = serializers.CharField(source='get_liability_type_display', read_only=True)
    
    class Meta:
        model = Liability
        fields = [
            'id', 'name', 'liability_type', 'liability_type_display', 'amount',
            'due_date', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EquitySerializer(serializers.ModelSerializer):
    equity_type_display = serializers.CharField(source='get_equity_type_display', read_only=True)
    
    class Meta:
        model = Equity
        fields = [
            'id', 'equity_type', 'equity_type_display', 'amount', 'date',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    model_type_display = serializers.CharField(source='get_model_type_display', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_name', 'user_email', 'action', 'action_display',
            'model_type', 'model_type_display', 'object_id', 'object_repr',
            'changes', 'ip_address', 'user_agent', 'endpoint', 'method',
            'is_suspicious', 'notes', 'timestamp'
        ]
        read_only_fields = fields  # All fields are read-only for audit logs

