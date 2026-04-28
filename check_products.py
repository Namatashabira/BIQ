import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'admin_panel.settings')
django.setup()

from product.models import Product

products = Product.objects.all()
print(f'\nTotal products in database: {products.count()}\n')

print('First 10 products:')
for p in products[:10]:
    print(f'  ID: {p.id} | Name: {p.name} | Category: {p.category or "N/A"} | Status: {p.status}')

# Search for "food"
food_products = products.filter(name__icontains='food')
print(f'\n\nProducts with "food" in name: {food_products.count()}')
for p in food_products:
    print(f'  ID: {p.id} | Name: {p.name} | Category: {p.category}')

# Search for "food" in category
food_category = products.filter(category__icontains='food')
print(f'\n\nProducts with "food" in category: {food_category.count()}')
for p in food_category:
    print(f'  ID: {p.id} | Name: {p.name} | Category: {p.category}')
