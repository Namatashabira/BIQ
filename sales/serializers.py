from rest_framework import serializers
from core.models import Order, OrderItem

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product_name', 'quantity', 'price']

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = Order
        fields = ['id', 'customer_name', 'customer_email', 'order_type', 'order_source', 'total', 'date', 'status', 'items']

class TopProductSerializer(serializers.Serializer):
    name = serializers.CharField()
    revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    units = serializers.IntegerField()
    orders = serializers.IntegerField()
    percentage = serializers.DecimalField(max_digits=5, decimal_places=1)

class CustomerInsightsSerializer(serializers.Serializer):
    new_customers = serializers.IntegerField()
    returning_customers = serializers.IntegerField()
    total_customers = serializers.IntegerField()
    avg_spend_new = serializers.DecimalField(max_digits=12, decimal_places=2)
    avg_spend_returning = serializers.DecimalField(max_digits=12, decimal_places=2)
    repeat_rate = serializers.DecimalField(max_digits=5, decimal_places=1)

class GeographicPerformanceSerializer(serializers.Serializer):
    location = serializers.CharField()
    total_sales = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_orders = serializers.IntegerField()
    avg_order_value = serializers.DecimalField(max_digits=12, decimal_places=2)

class SalesOperationsSerializer(serializers.Serializer):
    daily_sales_velocity = serializers.DecimalField(max_digits=12, decimal_places=2)
    completion_rate = serializers.DecimalField(max_digits=5, decimal_places=1)
    cancellation_rate = serializers.DecimalField(max_digits=5, decimal_places=1)
    pending_orders = serializers.IntegerField()
    total_orders = serializers.IntegerField()

class RecentOrderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    customer_name = serializers.CharField()
    customer_email = serializers.EmailField()
    order_type = serializers.CharField()
    order_source = serializers.CharField()
    items_count = serializers.IntegerField()
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
    status = serializers.CharField()
    date = serializers.CharField()

class SalesDashboardSerializer(serializers.Serializer):
    total_sales = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_orders = serializers.IntegerField()
    units_sold = serializers.IntegerField()
    average_order_value = serializers.DecimalField(max_digits=12, decimal_places=2)
    retail_sales = serializers.DecimalField(max_digits=12, decimal_places=2)
    wholesale_sales = serializers.DecimalField(max_digits=12, decimal_places=2)
    retail_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    wholesale_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    current_sales = serializers.DecimalField(max_digits=12, decimal_places=2)
    previous_sales = serializers.DecimalField(max_digits=12, decimal_places=2)
    growth_percentage = serializers.DecimalField(max_digits=5, decimal_places=2)
    top_products = TopProductSerializer(many=True)
    customer_insights = CustomerInsightsSerializer()
    geographic_performance = GeographicPerformanceSerializer(many=True)
    sales_operations = SalesOperationsSerializer()
    recent_orders = RecentOrderSerializer(many=True)

class SalesTrendSerializer(serializers.Serializer):
    period = serializers.CharField()
    sales = serializers.DecimalField(max_digits=12, decimal_places=2)
    orders_count = serializers.IntegerField()