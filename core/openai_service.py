"""
OpenAI Integration Service
Provides AI-powered suggestions based on business data
"""
import os
import json
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Sum, Avg, Count
from decimal import Decimal

# OpenAI client (install with: pip install openai)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("⚠️ OpenAI not installed. Run: pip install openai")


class OpenAIBusinessAssistant:
    """
    AI-powered business intelligence using OpenAI GPT models
    """
    
    def __init__(self, api_key=None):
        """Initialize OpenAI client with API key"""
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.client = None
        self.model = "gpt-4-turbo-preview"  # or gpt-3.5-turbo for lower cost
        
        if OPENAI_AVAILABLE and self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            print("⚠️ OpenAI API key not configured")
    
    def is_available(self):
        """Check if OpenAI is properly configured"""
        return OPENAI_AVAILABLE and self.client is not None
    
    def _prepare_business_data(self, orders, products, customers_data=None):
        """Convert Django models to JSON-serializable summary"""
        # Sales summary
        total_revenue = sum(float(o.total) for o in orders)
        avg_order_value = total_revenue / len(orders) if orders else 0
        
        # Product summary
        product_sales = {}
        for order in orders:
            for item in order.items.all():
                if item.product_name not in product_sales:
                    product_sales[item.product_name] = {
                        'quantity': 0,
                        'revenue': 0
                    }
                product_sales[item.product_name]['quantity'] += item.quantity
                product_sales[item.product_name]['revenue'] += float(item.price * item.quantity)
        
        # Top products
        top_products = sorted(
            product_sales.items(),
            key=lambda x: x[1]['revenue'],
            reverse=True
        )[:10]
        
        # Inventory status
        low_stock_products = [
            {'name': p.name, 'stock': p.stock}
            for p in products if p.stock < 10
        ]
        
        return {
            'period': '30 days',
            'total_orders': len(orders),
            'total_revenue': round(total_revenue, 2),
            'average_order_value': round(avg_order_value, 2),
            'top_products': [
                {'name': name, 'quantity_sold': data['quantity'], 'revenue': round(data['revenue'], 2)}
                for name, data in top_products
            ],
            'low_stock_items': low_stock_products,
            'total_products': len(products),
            'customers_data': customers_data or {}
        }
    
    def get_business_insights(self, orders, products):
        """
        Get comprehensive business insights from OpenAI
        """
        if not self.is_available():
            return {
                'success': False,
                'error': 'OpenAI not configured. Please set OPENAI_API_KEY environment variable.'
            }
        
        try:
            # Prepare data summary
            business_data = self._prepare_business_data(orders, products)
            
            # Create prompt
            prompt = f"""
You are a business intelligence analyst. Analyze this business data and provide actionable insights:

Business Summary:
- Period: {business_data['period']}
- Total Orders: {business_data['total_orders']}
- Total Revenue: ${business_data['total_revenue']:,.2f}
- Average Order Value: ${business_data['average_order_value']:.2f}
- Total Products: {business_data['total_products']}

Top Selling Products:
{json.dumps(business_data['top_products'][:5], indent=2)}

Low Stock Items:
{json.dumps(business_data['low_stock_items'][:5], indent=2)}

Provide:
1. Key insights about sales performance
2. Product recommendations (what to stock more/less)
3. Pricing optimization suggestions
4. Customer engagement strategies
5. Inventory management recommendations

Format as clear, actionable bullet points.
"""
            
            # Call OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert business analyst specializing in retail and e-commerce optimization."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            insights = response.choices[0].message.content
            
            return {
                'success': True,
                'insights': insights,
                'business_data': business_data,
                'tokens_used': response.usage.total_tokens
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'OpenAI API error: {str(e)}'
            }
    
    def get_product_recommendations(self, customer_history, all_products):
        """
        Get personalized product recommendations for a customer
        """
        if not self.is_available():
            return {
                'success': False,
                'error': 'OpenAI not configured'
            }
        
        try:
            # Prepare customer purchase history
            purchased_products = [
                item.product_name
                for order in customer_history
                for item in order.items.all()
            ]
            
            available_products = [p.name for p in all_products if p.stock > 0]
            
            prompt = f"""
Based on this customer's purchase history, recommend 5 products they might like:

Previously Purchased:
{', '.join(purchased_products[:10])}

Available Products:
{', '.join(available_products[:20])}

Provide recommendations with brief explanations.
"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a product recommendation expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=500
            )
            
            return {
                'success': True,
                'recommendations': response.choices[0].message.content
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_inventory_strategy(self, inventory_data, sales_data):
        """
        Generate smart inventory management strategy
        """
        if not self.is_available():
            return {
                'success': False,
                'error': 'OpenAI not configured'
            }
        
        try:
            prompt = f"""
As an inventory management expert, analyze this data and provide a strategic plan:

Current Inventory:
{json.dumps(inventory_data[:10], indent=2)}

Recent Sales Patterns:
{json.dumps(sales_data, indent=2)}

Provide:
1. Which products to reorder immediately
2. Optimal reorder quantities
3. Products to promote/discount
4. Seasonal considerations
5. Risk mitigation strategies

Be specific and actionable.
"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an inventory optimization specialist."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                max_tokens=800
            )
            
            return {
                'success': True,
                'strategy': response.choices[0].message.content
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_customer_message(self, customer_name, order_history, message_type='followup'):
        """
        Generate personalized customer communication
        message_type: 'followup', 'promotion', 'reengagement', 'thankyou'
        """
        if not self.is_available():
            return {
                'success': False,
                'error': 'OpenAI not configured'
            }
        
        try:
            prompts = {
                'followup': f"Write a friendly follow-up email to {customer_name} about their recent purchase. Keep it warm and professional.",
                'promotion': f"Write a promotional message for {customer_name} based on their purchase history. Offer relevant products.",
                'reengagement': f"Write a re-engagement email to {customer_name} who hasn't ordered in a while. Make it compelling.",
                'thankyou': f"Write a thank you message to {customer_name} for being a loyal customer."
            }
            
            prompt = prompts.get(message_type, prompts['followup'])
            prompt += f"\n\nTheir recent purchases: {', '.join([o.items.first().product_name for o in order_history[:3] if o.items.exists()])}"
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a customer relationship expert who writes engaging, personalized messages."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=300
            )
            
            return {
                'success': True,
                'message': response.choices[0].message.content
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def analyze_sales_trends(self, sales_data_text):
        """
        Get insights on sales trends and patterns
        """
        if not self.is_available():
            return {
                'success': False,
                'error': 'OpenAI not configured'
            }
        
        try:
            prompt = f"""
Analyze these sales trends and identify patterns:

{sales_data_text}

Provide:
1. Notable trends (increasing/decreasing)
2. Seasonal patterns
3. Anomalies or concerns
4. Growth opportunities
5. Action items for the business owner

Keep it concise and actionable.
"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a data analyst specializing in sales trend analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                max_tokens=600
            )
            
            return {
                'success': True,
                'analysis': response.choices[0].message.content
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
