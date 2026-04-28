# Django management command to remove duplicate products by (tenant, name)
from django.core.management.base import BaseCommand
from django.db import connection
from product.models import Product

class Command(BaseCommand):
    help = 'Remove duplicate products by (tenant, name), keeping only the earliest created.'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT tenant_id, name
                FROM product_product
                GROUP BY tenant_id, name
                HAVING COUNT(*) > 1
            ''')
            duplicates = cursor.fetchall()
        if not duplicates:
            self.stdout.write(self.style.SUCCESS('No duplicates found.'))
            return
        for tenant_id, name in duplicates:
            products = list(Product.objects.filter(tenant_id=tenant_id, name=name).order_by('id'))
            # Keep the first, delete the rest
            to_delete = products[1:]
            count = len(to_delete)
            for product in to_delete:
                product.delete()
            self.stdout.write(self.style.WARNING(f'Removed {count} duplicate(s) for tenant_id={tenant_id}, name="{name}"'))
        self.stdout.write(self.style.SUCCESS('Duplicate removal complete.'))
