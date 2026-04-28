from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal
import random
from datetime import timedelta
from sales.models import Customer, Product, Order, OrderItem

class Command(BaseCommand):
    help = 'Create sample sales data for testing'

    def handle(self, *args, **options):
        self.stdout.write('Creating sample sales data...')
        
        # Create customers
        customers = []
        for i in range(20):
            customer = Customer.objects.create(
                name=f'Customer {i+1}',
                email=f'customer{i+1}@example.com',
                phone=f'+256700{i+1:06d}',
                customer_type='retail' if i % 3 != 0 else 'wholesale'
            )
            customers.append(customer)
        
        # Create products
        products = []
        product_data = [
            ('Premium Seeds Pack', 'SEED001', Decimal('25000'), Decimal('20000')),
            ('Organic Fertilizer 50kg', 'FERT001', Decimal('150000'), Decimal('120000')),
            ('Herbicide Pro 5L', 'HERB001', Decimal('85000'), Decimal('70000')),
            ('NPK Fertilizer Bulk', 'FERT002', Decimal('180000'), Decimal('150000')),
            ('Insecticide Spray', 'PEST001', Decimal('45000'), Decimal('38000')),
            ('Tomato Seeds', 'SEED002', Decimal('15000'), Decimal('12000')),
            ('Cabbage Seeds', 'SEED003', Decimal('18000'), Decimal('15000')),
            ('Fungicide 1L', 'FUNG001', Decimal('65000'), Decimal('55000')),
        ]
        
        for name, sku, retail, wholesale in product_data:
            product = Product.objects.create(
                name=name,
                sku=sku,
                retail_price=retail,
                wholesale_price=wholesale
            )
            products.append(product)
        
        # Create orders for the last 90 days
        for i in range(100):
            # Random date in the last 90 days
            days_ago = random.randint(0, 90)
            order_date = timezone.now() - timedelta(days=days_ago)
            
            customer = random.choice(customers)
            
            order = Order.objects.create(
                customer=customer,
                order_number=f'ORD-{1000 + i}',
                status=random.choice(['pending', 'confirmed', 'shipped', 'delivered']),
                created_at=order_date
            )
            
            # Add 1-5 items to each order
            total_amount = Decimal('0.00')
            for _ in range(random.randint(1, 5)):
                product = random.choice(products)
                quantity = random.randint(1, 10)
                
                # Use appropriate price based on customer type
                unit_price = product.wholesale_price if customer.customer_type == 'wholesale' else product.retail_price
                
                order_item = OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=quantity * unit_price
                )
                
                total_amount += order_item.total_price
            
            # Update order total
            order.total_amount = total_amount
            order.save()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created:\n'
                f'- {len(customers)} customers\n'
                f'- {len(products)} products\n'
                f'- 100 orders with items'
            )
        )