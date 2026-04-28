# serializers.py
from rest_framework import serializers
from core.models import Order, OrderItem

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product_name', 'quantity', 'price']
        read_only_fields = ['id']

class OrderSerializer(serializers.ModelSerializer):
    # Frontend sends order data to the backend via API
    order_items = OrderItemSerializer(many=True, write_only=True, required=False)
    # For GET: return detailed items
    items = OrderItemSerializer(many=True, read_only=True)
    # For single product orders (legacy support)
    product_name = serializers.CharField(required=False)
    quantity = serializers.IntegerField(required=False)

    class Meta:
        model = Order
        fields = [
            'id', 'customer_name', 'customer_email', 'phone_number', 
            'location', 'order_type', 'delivery', 'total', 'status', 
            'date', 'order_items', 'items', 'product_name', 'quantity',
            'order_source', 'created_by', 'tenant'
        ]
        read_only_fields = ['id', 'date', 'items', 'created_by', 'tenant']

    def create(self, validated_data):
        request = self.context.get('request') if hasattr(self, 'context') else None
        if request and getattr(request, 'user', None) and request.user.is_authenticated:
            validated_data['created_by'] = request.user
            # Stamp tenant directly on the order
            tenant = getattr(request.user, 'tenant', None)
            if not tenant and hasattr(request.user, 'tenant_id') and request.user.tenant_id:
                from tenants.models import Tenant
                tenant = Tenant.objects.filter(id=request.user.tenant_id).first()
            if tenant:
                validated_data['tenant'] = tenant

        # Extract the items sent from frontend
        order_items_data = validated_data.pop('order_items', [])
        product_name = validated_data.pop('product_name', None)
        quantity = validated_data.pop('quantity', None)
        
        # Backend saves order in database with a default status (Pending)
        if 'status' not in validated_data:
            validated_data['status'] = 'pending'
        order = Order.objects.create(**validated_data)

        # Handle single product (legacy) or multiple items
        total = 0
        if product_name and quantity:
            # Single product order (legacy support)
            price = validated_data.get('total', 0) / quantity if quantity > 0 else 0
            OrderItem.objects.create(
                order=order, 
                product_name=product_name, 
                quantity=quantity, 
                price=price
            )
            total = validated_data.get('total', 0)
        else:
            # Multiple items order
            for item_data in order_items_data:
                quantity = item_data.get('quantity', 0)
                price = item_data.get('price', 0)
                total += quantity * price
                OrderItem.objects.create(order=order, **item_data)

        # Update order total
        order.total = total
        order.save(update_fields=['total'])

        return order
