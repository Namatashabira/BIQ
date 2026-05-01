from rest_framework import serializers
from .models import Plan, TenantSubscription


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
