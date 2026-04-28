"""
OpenAI-powered API endpoints
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from .models import Order
from product.models import Product
from .openai_service import OpenAIBusinessAssistant
import os


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def openai_business_insights(request):
    """
    Get comprehensive business insights from OpenAI
    """
    try:
        # Get API key from environment or settings
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return Response({
                'success': False,
                'error': 'OpenAI API key not configured. Please set OPENAI_API_KEY in environment variables.',
                'setup_instructions': {
                    'step1': 'Get API key from https://platform.openai.com/api-keys',
                    'step2': 'Set environment variable: OPENAI_API_KEY=sk-your-key-here',
                    'step3': 'Restart Django server'
                }
            })
        
        # Get recent orders and products
        days_back = int(request.GET.get('days_back', 30))
        start_date = timezone.now() - timedelta(days=days_back)
        
        orders = Order.objects.filter(
            date__gte=start_date
        ).prefetch_related('items')
        
        products = Product.objects.all()
        
        # Initialize OpenAI assistant
        assistant = OpenAIBusinessAssistant(api_key=api_key)
        
        # Get insights
        result = assistant.get_business_insights(orders, products)
        
        return Response(result)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': f'Error generating insights: {str(e)}'
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def openai_product_recommendations(request):
    """
    Get personalized product recommendations for a customer
    """
    try:
        customer_email = request.GET.get('customer_email')
        if not customer_email:
            return Response({
                'success': False,
                'error': 'customer_email parameter required'
            }, status=400)
        
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return Response({
                'success': False,
                'error': 'OpenAI API key not configured'
            })
        
        # Get customer order history
        customer_orders = Order.objects.filter(
            customer_email=customer_email
        ).prefetch_related('items').order_by('-date')[:10]
        
        if not customer_orders.exists():
            return Response({
                'success': False,
                'error': 'No order history found for this customer'
            })
        
        # Get all available products
        products = Product.objects.filter(stock__gt=0)
        
        # Get recommendations
        assistant = OpenAIBusinessAssistant(api_key=api_key)
        result = assistant.get_product_recommendations(customer_orders, products)
        
        return Response(result)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def openai_inventory_strategy(request):
    """
    Generate inventory management strategy
    """
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return Response({
                'success': False,
                'error': 'OpenAI API key not configured'
            })
        
        # Get inventory data
        products = Product.objects.all()
        inventory_data = [
            {
                'name': p.name,
                'stock': p.stock,
                'price': float(p.price) if hasattr(p, 'price') else 0
            }
            for p in products
        ]
        
        # Get recent sales data
        days_back = 30
        start_date = timezone.now() - timedelta(days=days_back)
        orders = Order.objects.filter(date__gte=start_date).prefetch_related('items')
        
        sales_summary = {
            'total_orders': orders.count(),
            'total_revenue': sum(float(o.total) for o in orders),
            'period': f'{days_back} days'
        }
        
        # Generate strategy
        assistant = OpenAIBusinessAssistant(api_key=api_key)
        result = assistant.generate_inventory_strategy(inventory_data, sales_summary)
        
        return Response(result)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def openai_customer_message(request):
    """
    Generate personalized customer message
    """
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return Response({
                'success': False,
                'error': 'OpenAI API key not configured'
            })
        
        customer_email = request.data.get('customer_email')
        message_type = request.data.get('message_type', 'followup')
        
        if not customer_email:
            return Response({
                'success': False,
                'error': 'customer_email required'
            }, status=400)
        
        # Get customer orders
        orders = Order.objects.filter(
            customer_email=customer_email
        ).prefetch_related('items').order_by('-date')[:5]
        
        if not orders.exists():
            return Response({
                'success': False,
                'error': 'No order history found'
            })
        
        customer_name = orders.first().customer_name
        
        # Generate message
        assistant = OpenAIBusinessAssistant(api_key=api_key)
        result = assistant.generate_customer_message(
            customer_name,
            orders,
            message_type
        )
        
        return Response(result)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def openai_sales_analysis(request):
    """
    Get detailed sales trend analysis
    """
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return Response({
                'success': False,
                'error': 'OpenAI API key not configured'
            })
        
        # Get sales data
        days_back = int(request.GET.get('days_back', 30))
        start_date = timezone.now() - timedelta(days=days_back)
        
        orders = Order.objects.filter(date__gte=start_date).order_by('date')
        
        # Prepare sales data text
        sales_text = f"Sales data for last {days_back} days:\n\n"
        sales_text += f"Total Orders: {orders.count()}\n"
        sales_text += f"Total Revenue: ${sum(float(o.total) for o in orders):,.2f}\n\n"
        
        # Daily breakdown
        from collections import defaultdict
        daily_sales = defaultdict(lambda: {'orders': 0, 'revenue': 0})
        
        for order in orders:
            date_key = order.date.strftime('%Y-%m-%d')
            daily_sales[date_key]['orders'] += 1
            daily_sales[date_key]['revenue'] += float(order.total)
        
        sales_text += "Daily Breakdown:\n"
        for date, data in sorted(daily_sales.items())[:10]:
            sales_text += f"{date}: {data['orders']} orders, ${data['revenue']:.2f}\n"
        
        # Analyze with OpenAI
        assistant = OpenAIBusinessAssistant(api_key=api_key)
        result = assistant.analyze_sales_trends(sales_text)
        
        return Response(result)
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)
