# Django management command to find duplicate products by (tenant, name)
from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Find duplicate products by (tenant, name) in the product_product table.'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT tenant_id, name, COUNT(*) as count
                FROM product_product
                GROUP BY tenant_id, name
                HAVING count > 1
            ''')
            duplicates = cursor.fetchall()
        if not duplicates:
            self.stdout.write(self.style.SUCCESS('No duplicates found.'))
            return
        self.stdout.write(self.style.WARNING('Duplicate products by (tenant, name):'))
        for tenant_id, name, count in duplicates:
            self.stdout.write(f'Tenant ID: {tenant_id}, Name: {name}, Count: {count}')
