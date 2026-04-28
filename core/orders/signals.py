from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Order
from product.models import Product
from django.core.exceptions import ValidationError


@receiver(pre_save, sender=Order)
def track_order_status_change(sender, instance, **kwargs):
    """Track the previous status before saving"""
    if instance.pk:
        try:
            old_order = Order.objects.get(pk=instance.pk)
            instance._previous_status = old_order.status
        except Order.DoesNotExist:
            instance._previous_status = None
    else:
        instance._previous_status = None
    
    # NOTE: Stock validation disabled because OrderItem doesn't have product FK
    # OrderItem only stores product_name, quantity, price as text fields
    # If you need stock management, add a product ForeignKey to OrderItem model


@receiver(post_save, sender=Order)
def broadcast_order_status_change(sender, instance, created, **kwargs):
    """Broadcast order status changes to users in real-time"""
    
    # NOTE: Stock management disabled because OrderItem doesn't have product FK
    # OrderItem only stores product_name, quantity, price as text fields
    # If you need stock management, add a product ForeignKey to OrderItem model
    
    if not created and hasattr(instance, '_previous_status'):
        # Only broadcast if status actually changed
        if instance._previous_status != instance.status:
            try:
                channel_layer = get_channel_layer()
                
                # Broadcast to user-specific channel
                user_group = f"user_{instance.customer_email}"
                async_to_sync(channel_layer.group_send)(
                    user_group,
                    {
                        "type": "order_status_update",
                        "message": {
                            "order_id": instance.id,
                            "customer_name": instance.customer_name,
                            "customer_email": instance.customer_email,
                            "status": instance.status,
                            "previous_status": instance._previous_status,
                            "total": str(instance.total),
                            "date": instance.date.isoformat(),
                            "notification_type": "status_change"
                        }
                    }
                )
                
                # Also broadcast to general orders channel for admin
                async_to_sync(channel_layer.group_send)(
                    "orders",
                    {
                        "type": "order_message",
                        "message": {
                            "id": instance.id,
                            "customer_name": instance.customer_name,
                            "customer_email": instance.customer_email,
                            "phone_number": instance.phone_number,
                            "location": instance.location,
                            "order_type": instance.order_type,
                            "delivery": instance.delivery,
                            "total": str(instance.total),
                            "status": instance.status,
                            "date": instance.date.isoformat(),
                            "notification_type": "status_update"
                        }
                    }
                )
            except Exception as e:
                print(f"WebSocket broadcast error: {e}")