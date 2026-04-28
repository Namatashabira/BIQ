from rest_framework import serializers
from .models import Tenant, OrderSyncConfig, Order

class OrderSyncConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderSyncConfig
        fields = ['enabled', 'field_mapping', 'last_updated']

class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            'id', 'customer_name', 'email', 'product_id', 'quantity', 'order_total',
            'raw_payload', 'created_at', 'status', 'error_message'
        ]

class IncomingOrderSerializer(serializers.Serializer):
    api_key = serializers.CharField()
    payload = serializers.DictField()


# Serializer for AllowedOrigin
from .models import AllowedOrigin

class AllowedOriginSerializer(serializers.ModelSerializer):
    class Meta:
        model = AllowedOrigin
        fields = ['id', 'origin', 'created_at']

class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ['id', 'name', 'api_key']
