"""
Test script to verify order creation and WebSocket notifications
"""
import os
import django
import sys

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'admin_panel.settings')
django.setup()

from core.models import Order, OrderItem
from django.db import transaction

def test_order_creation():
    """Test creating an order"""
    print("=" * 60)
    print("TESTING ORDER CREATION")
    print("=" * 60)
    
    # Count existing orders
    initial_count = Order.objects.count()
    print(f"\n📊 Current orders in database: {initial_count}")
    
    # Create a test order
    try:
        with transaction.atomic():
            order = Order.objects.create(
                customer_name="Test User",
                customer_email="test@example.com",
                phone_number="1234567890",
                location="Test Location",
                order_type="retail",
                order_source="user",
                delivery=False,
                total=0,
                status="pending"
            )
            
            # Add items
            item1 = OrderItem.objects.create(
                order=order,
                product_name="Test Product 1",
                quantity=2,
                price=10.00
            )
            
            item2 = OrderItem.objects.create(
                order=order,
                product_name="Test Product 2",
                quantity=1,
                price=25.50
            )
            
            # Update total
            order.total = (item1.quantity * item1.price) + (item2.quantity * item2.price)
            order.save(update_fields=['total'])
            
            print(f"\n✅ Order created successfully!")
            print(f"   Order ID: {order.id}")
            print(f"   Customer: {order.customer_name} ({order.customer_email})")
            print(f"   Status: {order.status}")
            print(f"   Total: ${order.total}")
            print(f"   Items: {order.items.count()}")
            
            for item in order.items.all():
                print(f"      - {item.product_name} x{item.quantity} @ ${item.price} = ${item.quantity * item.price}")
    
    except Exception as e:
        print(f"\n❌ Error creating order: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Verify count increased
    final_count = Order.objects.count()
    print(f"\n📊 Orders after creation: {final_count}")
    print(f"   Orders added: {final_count - initial_count}")
    
    return True

def list_recent_orders():
    """List the 5 most recent orders"""
    print("\n" + "=" * 60)
    print("RECENT ORDERS IN DATABASE")
    print("=" * 60)
    
    orders = Order.objects.all().order_by('-date')[:5]
    
    if not orders:
        print("\n⚠️  No orders found in database")
        return
    
    for order in orders:
        print(f"\n📦 Order #{order.id}")
        print(f"   Customer: {order.customer_name} ({order.customer_email})")
        print(f"   Status: {order.status.upper()}")
        print(f"   Total: ${order.total}")
        print(f"   Date: {order.date}")
        print(f"   Items: {order.items.count()}")
        for item in order.items.all():
            print(f"      - {item.product_name} x{item.quantity} @ ${item.price}")

def test_websocket_group():
    """Test if channel layer is working"""
    print("\n" + "=" * 60)
    print("TESTING WEBSOCKET CHANNEL LAYER")
    print("=" * 60)
    
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        print(f"\n✅ Channel layer initialized: {channel_layer}")
        print(f"   Backend: {channel_layer.__class__.__name__}")
        
        # Try to send a test message
        try:
            async_to_sync(channel_layer.group_send)(
                'test_group',
                {
                    'type': 'test_message',
                    'message': 'Hello from test script'
                }
            )
            print(f"\n✅ Successfully sent test message to 'test_group'")
            print(f"   Note: No error means channel layer is working")
            print(f"   (Message won't be received unless a consumer is connected)")
        except Exception as e:
            print(f"\n❌ Failed to send message: {e}")
            
    except Exception as e:
        print(f"\n❌ Channel layer error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("\n🚀 Starting Order System Tests\n")
    
    # Test order creation
    if test_order_creation():
        print("\n✅ Order creation test PASSED")
    else:
        print("\n❌ Order creation test FAILED")
    
    # List recent orders
    list_recent_orders()
    
    # Test WebSocket
    test_websocket_group()
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS COMPLETED")
    print("=" * 60)
