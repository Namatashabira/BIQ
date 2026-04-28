import requests

try:
    response = requests.get('http://127.0.0.1:8000/api/products/')
    print(f'Status Code: {response.status_code}')
    print(f'Total products returned: {len(response.json())}')
    print('\nFirst 5 products:')
    for product in response.json()[:5]:
        print(f'  {product["id"]}: {product["name"]} - Category: {product.get("category", "N/A")}')
    
    # Check for "Food"
    products = response.json()
    food_products = [p for p in products if 'food' in p['name'].lower()]
    print(f'\n\nProducts with "food" in name: {len(food_products)}')
    for p in food_products:
        print(f'  {p["id"]}: {p["name"]}')
except Exception as e:
    print(f'Error: {e}')
