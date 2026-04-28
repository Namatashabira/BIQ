from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Order, OrderItem
from product.models import Product
from django.core.exceptions import ValidationError


@receiver(pre_save, sender=Order)
def validate_order_products(sender, instance, **kwargs):
    """Validate products before order is saved"""
    if instance.pk:  # Only for updates
        old_instance = Order.objects.filter(pk=instance.pk).first()
        if old_instance and old_instance.order_status != 'confirmed' and instance.order_status == 'confirmed':
            # Order is being confirmed, validate products
            print(f"[Order Signal] Validating products for order {instance.order_number}")
            for item in instance.items.all():
                product = item.product
                if product.is_expired():
                    raise ValidationError(f"Cannot confirm order: Product '{product.name}' is expired")
                if product.stock < item.quantity:
                    raise ValidationError(f"Cannot confirm order: Insufficient stock for '{product.name}'. Available: {product.stock}, Required: {item.quantity}")


@receiver(post_save, sender=Order)
def handle_order_stock_deduction(sender, instance, created, **kwargs):
    """Automatically deduct stock when order is confirmed"""
    # Only process if order status is 'confirmed' or 'paid'
    if instance.order_status in ['confirmed', 'paid']:
        # Check if this is a status change to confirmed/paid
        if instance.pk:
            old_instance = Order.objects.filter(pk=instance.pk).first()
            if old_instance and old_instance.order_status not in ['confirmed', 'paid']:
                print(f"[Order Signal] Order {instance.order_number} confirmed/paid. Deducting stock...")
                
                for item in instance.items.all():
                    product = item.product
                    try:
                        product.deduct_stock(item.quantity, reason=f"Order {instance.order_number}")
                        print(f"[Order Signal] Deducted {item.quantity} units of {product.name}")
                    except ValueError as e:
                        print(f"[Order Signal] Error deducting stock for {product.name}: {str(e)}")
                        # You might want to handle this error - e.g., cancel the order or alert admin


@receiver(post_save, sender=Order)
def handle_order_cancellation_stock_return(sender, instance, created, **kwargs):
    """Return stock when order is cancelled"""
    if instance.order_status == 'cancelled':
        if instance.pk:
            old_instance = Order.objects.filter(pk=instance.pk).first()
            if old_instance and old_instance.order_status != 'cancelled':
                print(f"[Order Signal] Order {instance.order_number} cancelled. Returning stock...")
                
                for item in instance.items.all():
                    product = item.product
                    try:
                        product.add_stock(item.quantity, reason=f"Order {instance.order_number} cancelled")
                        print(f"[Order Signal] Returned {item.quantity} units of {product.name}")
                    except ValueError as e:
                        print(f"[Order Signal] Error returning stock for {product.name}: {str(e)}")
