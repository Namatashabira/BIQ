from rest_framework import serializers
from .models import Plan, TenantSubscription, PaymentRequest


class PlanSerializer(serializers.ModelSerializer):
    product_limit_display = serializers.ReadOnlyField()

    class Meta:
        model = Plan
        fields = ['id', 'key', 'name', 'price_ugx', 'trial_days', 'product_limit', 'product_limit_display', 'allowed_pages']


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    is_trial_expired = serializers.ReadOnlyField()
    days_left = serializers.ReadOnlyField()

    class Meta:
        model = TenantSubscription
        fields = ['id', 'plan', 'status', 'trial_start', 'trial_end', 'is_trial_expired', 'days_left', 'started_at']


class PaymentRequestSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_key = serializers.CharField(source='plan.key', read_only=True)
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)

    class Meta:
        model = PaymentRequest
        fields = [
            'id', 'tenant_name', 'plan_name', 'plan_key',
            'sender_name', 'phone_number', 'payment_method',
            'transaction_id', 'status', 'activation_code',
            'code_expires_at', 'code_used', 'admin_note', 'created_at', 'updated_at',
        ]
        read_only_fields = ['activation_code', 'code_expires_at', 'code_used', 'status', 'created_at', 'updated_at']
