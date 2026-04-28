from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from .ai_analytics import AIAnalytics
from .models import Order, Receipt
from product.models import Product
from django.db.models import Sum
from tenants.models import Tenant


def _resolve_tenant(request):
    user = request.user
    tenant = getattr(user, 'tenant', None)
    if not tenant:
        tenant = Tenant.objects.filter(admin=user).first()
        if tenant:
            user.tenant = tenant
            user.save(update_fields=['tenant'])
    return tenant


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_sales_forecast(request):
    try:
        tenant = _resolve_tenant(request)
        if not tenant and not request.user.is_superuser:
            return Response({'success': False, 'error': 'No tenant found.'}, status=403)

        days_back = int(request.GET.get('days_back', 90))
        days_ahead = int(request.GET.get('days_ahead', 30))
        start_date = timezone.now() - timedelta(days=days_back)

        qs = Order.objects.filter(
            date__gte=start_date,
            status__in=['confirmed', 'delivered']
        )
        if tenant:
            qs = qs.filter(tenant=tenant)

        orders = (
            qs.extra(select={'order_date': 'DATE(date)'})
            .values('order_date')
            .annotate(total=Sum('total'))
            .order_by('order_date')
        )

        orders_data = [
            {'date': str(o['order_date']), 'total': float(o['total']) if o['total'] else 0}
            for o in orders
        ]

        return Response({'success': True, 'data': AIAnalytics.sales_forecast(orders_data, days_ahead)})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_inventory_optimization(request):
    try:
        tenant = _resolve_tenant(request)
        if not tenant and not request.user.is_superuser:
            return Response({'success': False, 'error': 'No tenant found.'}, status=403)

        products_qs = Product.objects.all()
        if tenant:
            products_qs = products_qs.filter(tenant=tenant)
        products_data = list(products_qs.values('id', 'name', 'stock', 'price', 'retail_price', 'wholesale_price'))

        start_date = timezone.now() - timedelta(days=30)
        orders_qs = Order.objects.filter(date__gte=start_date)
        if tenant:
            orders_qs = orders_qs.filter(tenant=tenant)

        orders_data = []
        for order in orders_qs.prefetch_related('items'):
            orders_data.append({
                'id': order.id,
                'created_at': order.date.isoformat(),
                'items': [{'product_name': i.product_name, 'quantity': i.quantity} for i in order.items.all()]
            })

        return Response({'success': True, 'data': AIAnalytics.inventory_optimization(products_data, orders_data)})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_customer_behavior(request):
    try:
        tenant = _resolve_tenant(request)
        if not tenant and not request.user.is_superuser:
            return Response({'success': False, 'error': 'No tenant found.'}, status=403)

        days_back = int(request.GET.get('days_back', 90))
        start_date = timezone.now() - timedelta(days=days_back)

        qs = Order.objects.filter(date__gte=start_date)
        if tenant:
            qs = qs.filter(tenant=tenant)

        orders_data = [
            {
                'customer_id': o['customer_email'] or o['customer_name'],
                'customer_name': o['customer_name'],
                'total': float(o['total']) if o['total'] else 0,
                'order_type': o['order_type'],
                'date': o['date'].isoformat(),
            }
            for o in qs.values('customer_name', 'customer_email', 'total', 'date', 'order_type')
        ]

        return Response({'success': True, 'data': AIAnalytics.customer_behavior_analysis(orders_data)})
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_profit_prediction(request):
    try:
        tenant = _resolve_tenant(request)
        if not tenant and not request.user.is_superuser:
            return Response({'success': False, 'error': 'No tenant found.'}, status=403)

        months_back = int(request.GET.get('months_back', 12))
        financial_data = []

        for i in range(months_back):
            month_start = timezone.now() - timedelta(days=30 * (i + 1))
            month_end = timezone.now() - timedelta(days=30 * i)

            qs = Order.objects.filter(
                date__gte=month_start,
                date__lt=month_end,
                status__in=['confirmed', 'delivered']
            )
            if tenant:
                qs = qs.filter(tenant=tenant)

            revenue = qs.aggregate(total=Sum('total'))['total'] or 0
            expense = float(revenue) * 0.7
            financial_data.append({
                'month': month_start.strftime('%Y-%m'),
                'revenue': float(revenue),
                'expense': expense,
                'profit': float(revenue) - expense,
            })

        financial_data.reverse()
        return Response({
            'success': True,
            'data': AIAnalytics.profit_loss_prediction(financial_data),
            'historical_data': financial_data,
        })
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_comprehensive_insights(request):
    try:
        tenant = _resolve_tenant(request)
        if not tenant and not request.user.is_superuser:
            return Response({'success': False, 'error': 'No tenant found.'}, status=403)

        start_date = timezone.now() - timedelta(days=30)

        orders_qs = Order.objects.filter(
            date__gte=start_date,
            status__in=['confirmed', 'delivered']
        )
        if tenant:
            orders_qs = orders_qs.filter(tenant=tenant)

        orders_data = [
            {'date': str(o['order_date']), 'total': float(o['total']) if o['total'] else 0}
            for o in orders_qs.extra(select={'order_date': 'DATE(date)'})
            .values('order_date').annotate(total=Sum('total')).order_by('order_date')
        ]

        forecast = AIAnalytics.sales_forecast(orders_data, 7)

        products_qs = Product.objects.all()
        if tenant:
            products_qs = products_qs.filter(tenant=tenant)
        products = list(products_qs.values('id', 'name', 'stock'))

        orders_inv_qs = Order.objects.filter(date__gte=start_date)
        if tenant:
            orders_inv_qs = orders_inv_qs.filter(tenant=tenant)
        orders_inv = [
            {'id': o.id, 'items': [{'product_name': i.product_name, 'quantity': i.quantity} for i in o.items.all()]}
            for o in orders_inv_qs.prefetch_related('items')
        ]

        inventory = AIAnalytics.inventory_optimization(products, orders_inv)

        return Response({
            'success': True,
            'data': {
                'sales_forecast': forecast,
                'inventory_alerts': inventory,
                'quick_insights': {
                    'sales_trend': forecast.get('trend', 'stable'),
                    'critical_inventory_count': len(inventory.get('critical_items', [])),
                    'forecast_confidence': forecast.get('confidence', 'medium'),
                    'next_7_days_prediction': sum(
                        item['predicted_sales'] for item in forecast.get('forecast', [])[:7]
                    ) if forecast.get('forecast') else 0,
                },
            },
        })
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)
