from django.core.management.base import BaseCommand
from website_config.models import Order as WebsiteOrder
from core.models import Order, OrderItem
from django.utils import timezone

class Command(BaseCommand):
    help = 'Process new website orders and create main Order objects.'

    def handle(self, *args, **options):
        new_orders = WebsiteOrder.objects.filter(status='received')
        for w_order in new_orders:
            # Map fields as needed for your main Order model
            order = Order.objects.create(
                customer_name=w_order.customer_name,
                email=w_order.email,
                product_id=w_order.product_id,
                quantity=w_order.quantity,
                order_total=w_order.order_total,
                created_at=timezone.now(),
                # Add any other required fields here
            )
            # Optionally create OrderItem, trigger notifications, etc.
            w_order.status = 'processed'
            w_order.save()
            self.stdout.write(self.style.SUCCESS(f'Processed website order {w_order.id} into main Order {order.id}'))
