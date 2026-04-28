from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Count, Avg
from core.orders.models import Order, OrderItem
from tenants.models import Tenant
from datetime import datetime, timedelta


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
def analytics_summary(request):
    tenant = _resolve_tenant(request)
    if not tenant and not request.user.is_superuser:
        return Response({'error': 'No tenant found for this user.'}, status=403)

    start_date = request.GET.get('start')
    end_date = request.GET.get('end')

    # Scope to tenant
    if request.user.is_superuser:
        orders_qs = Order.objects.all()
    else:
        orders_qs = Order.objects.filter(tenant=tenant)

    if start_date and end_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            orders_qs = orders_qs.filter(date__range=[start, end])
        except ValueError:
            pass

    total_orders = orders_qs.count()
    total_revenue = orders_qs.aggregate(Sum('total'))['total__sum'] or 0
    avg_order_value = orders_qs.aggregate(Avg('total'))['total__avg'] or 0

    status_distribution = {
        item['status']: item['count']
        for item in orders_qs.values('status').annotate(count=Count('id'))
    }
    order_types = {
        item['order_type']: item['count']
        for item in orders_qs.values('order_type').annotate(count=Count('id'))
    }

    order_items = OrderItem.objects.filter(order__in=orders_qs)
    product_sales = order_items.values('product_name').annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum('price')
    ).order_by('-total_revenue')[:10]

    fulfilled_orders = orders_qs.filter(status__in=['delivered', 'confirmed']).count()
    fulfillment_rate = fulfilled_orders / total_orders if total_orders > 0 else 0

    monthly_data = []
    for i in range(12):
        month_start = datetime.now().replace(day=1) - timedelta(days=30 * i)
        month_end = month_start + timedelta(days=30)
        month_orders = orders_qs.filter(date__range=[month_start.date(), month_end.date()])
        monthly_data.append({
            'month': month_start.strftime('%Y-%m'),
            'orders': month_orders.count(),
            'revenue': month_orders.aggregate(Sum('total'))['total__sum'] or 0
        })

    customer_orders = orders_qs.values('customer_email').annotate(
        order_count=Count('id'),
        total_spent=Sum('total')
    ).order_by('-total_spent')[:10]

    location_data = orders_qs.values('location').annotate(
        order_count=Count('id'),
        total_revenue=Sum('total')
    ).order_by('-order_count')[:10]

    return Response({
        'summary': {
            'total_orders': total_orders,
            'total_revenue': float(total_revenue),
            'avg_order_value': float(avg_order_value),
            'fulfillment_rate': fulfillment_rate,
            'growth_rate': 0.15
        },
        'orders': {
            'status_distribution': status_distribution,
            'order_types': order_types,
            'monthly_trends': monthly_data
        },
        'products': {
            'top_products': list(product_sales),
            'total_products': order_items.values('product_name').distinct().count()
        },
        'customers': {
            'top_customers': list(customer_orders),
            'total_customers': orders_qs.values('customer_email').distinct().count()
        },
        'locations': {
            'top_locations': list(location_data)
        },
        'financial': {
            'total_revenue': float(total_revenue),
            'estimated_expenses': float(total_revenue) * 0.7,
            'estimated_profit': float(total_revenue) * 0.3,
            'tax_collected': float(total_revenue) * 0.18,
        }
    })
