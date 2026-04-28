# Script to find duplicate products by (tenant, name)
from django.contrib.auth import get_user_model
from core.models import Order
from product.models import Product
from django.db import connection


User = get_user_model()

# Find duplicates by (tenant, name)
def find_duplicates():
    with connection.cursor() as cursor:
        cursor.execute('''
            SELECT tenant_id, name, COUNT(*) as count
            FROM product_product
            GROUP BY tenant_id, name
            HAVING count > 1
        ''')
        return cursor.fetchall()

def print_duplicates():
    duplicates = find_duplicates()
    if not duplicates:
        print('No duplicates found.')
        return
    print('Duplicate products by (tenant, name):')
    for tenant_id, name, count in duplicates:
        print(f'Tenant ID: {tenant_id}, Name: {name}, Count: {count}')

if __name__ == '__main__':
    print_duplicates()
