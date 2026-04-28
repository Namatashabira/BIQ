from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from core.models import Order, OrderItem


class SalesService:

    @staticmethod
    def _base_qs(tenant):
        """All non-cancelled orders scoped to tenant."""
        qs = Order.objects.exclude(status='cancelled')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    @staticmethod
    def get_orders_in_range(tenant, start_date=None, end_date=None, customer_type=None):
        qs = SalesService._base_qs(tenant)
        if start_date:
            qs = qs.filter(date__gte=start_date)
        if end_date:
            qs = qs.filter(date__lte=end_date)
        if customer_type:
            qs = qs.filter(order_type=customer_type)
        return qs

    @staticmethod
    def get_total_sales(tenant, start_date=None, end_date=None, customer_type=None):
        orders = SalesService.get_orders_in_range(tenant, start_date, end_date, customer_type)
        return orders.aggregate(total=Sum('total'))['total'] or Decimal('0.00')

    @staticmethod
    def get_total_orders(tenant, start_date=None, end_date=None, customer_type=None):
        return SalesService.get_orders_in_range(tenant, start_date, end_date, customer_type).count()

    @staticmethod
    def get_units_sold(tenant, start_date=None, end_date=None, customer_type=None):
        orders = SalesService.get_orders_in_range(tenant, start_date, end_date, customer_type)
        return OrderItem.objects.filter(order__in=orders).aggregate(total=Sum('quantity'))['total'] or 0

    @staticmethod
    def get_average_order_value(tenant, start_date=None, end_date=None, customer_type=None):
        orders = SalesService.get_orders_in_range(tenant, start_date, end_date, customer_type)
        return orders.aggregate(avg=Avg('total'))['avg'] or Decimal('0.00')

    @staticmethod
    def get_sales_split(tenant, start_date=None, end_date=None):
        retail = SalesService.get_total_sales(tenant, start_date, end_date, 'retail')
        wholesale = SalesService.get_total_sales(tenant, start_date, end_date, 'wholesale')
        total = retail + wholesale
        if total > 0:
            retail_pct = (retail / total) * 100
            wholesale_pct = (wholesale / total) * 100
        else:
            retail_pct = wholesale_pct = Decimal('0.00')
        return {
            'retail_sales': retail,
            'wholesale_sales': wholesale,
            'retail_percentage': round(retail_pct, 2),
            'wholesale_percentage': round(wholesale_pct, 2),
        }

    @staticmethod
    def get_sales_growth(tenant, start_date, end_date):
        current = SalesService.get_total_sales(tenant, start_date, end_date)
        period = end_date - start_date
        prev_start = start_date - period
        previous = SalesService.get_total_sales(tenant, prev_start, start_date)
        if previous > 0:
            growth = ((current - previous) / previous) * 100
        else:
            growth = Decimal('0.00') if current == 0 else Decimal('100.00')
        return {
            'current_sales': current,
            'previous_sales': previous,
            'growth_percentage': round(growth, 2),
        }

    @staticmethod
    def get_sales_trend(tenant, start_date, end_date, group_by='day'):
        orders = SalesService.get_orders_in_range(tenant, start_date, end_date)
        select = "DATE_FORMAT(date, '%%Y-%%m')" if group_by == 'month' else "DATE(date)"
        return list(
            orders.extra(select={'period': select})
            .values('period')
            .annotate(sales=Sum('total'), orders_count=Count('id'))
            .order_by('period')
        )

    @staticmethod
    def get_top_products(tenant, start_date=None, end_date=None, limit=10):
        orders = SalesService.get_orders_in_range(tenant, start_date, end_date)
        products = (
            OrderItem.objects.filter(order__in=orders)
            .values('product_name')
            .annotate(
                total_revenue=Sum(F('quantity') * F('price')),
                total_units=Sum('quantity'),
                order_count=Count('order', distinct=True),
            )
            .order_by('-total_revenue')[:limit]
        )
        total_sales = SalesService.get_total_sales(tenant, start_date, end_date)
        result = []
        for p in products:
            pct = (p['total_revenue'] / total_sales * 100) if total_sales > 0 else 0
            result.append({
                'name': p['product_name'],
                'revenue': p['total_revenue'],
                'units': p['total_units'],
                'orders': p['order_count'],
                'percentage': round(pct, 1),
            })
        return result

    @staticmethod
    def get_customer_insights(tenant, start_date=None, end_date=None):
        orders = SalesService.get_orders_in_range(tenant, start_date, end_date)
        customers = orders.values('customer_email').annotate(
            total_orders=Count('id'),
            total_spent=Sum('total'),
            avg_order_value=Avg('total'),
        )
        new = sum(1 for c in customers if c['total_orders'] == 1)
        returning = sum(1 for c in customers if c['total_orders'] > 1)
        total = customers.count()
        repeat_rate = (returning / total * 100) if total > 0 else 0
        avg_new = orders.filter(
            customer_email__in=customers.filter(total_orders=1).values('customer_email')
        ).aggregate(avg=Avg('total'))['avg'] or Decimal('0.00')
        avg_ret = orders.filter(
            customer_email__in=customers.filter(total_orders__gt=1).values('customer_email')
        ).aggregate(avg=Avg('total'))['avg'] or Decimal('0.00')
        return {
            'new_customers': new,
            'returning_customers': returning,
            'total_customers': total,
            'avg_spend_new': avg_new,
            'avg_spend_returning': avg_ret,
            'repeat_rate': round(repeat_rate, 1),
        }

    @staticmethod
    def get_geographic_performance(tenant, start_date=None, end_date=None):
        orders = SalesService.get_orders_in_range(tenant, start_date, end_date)
        return list(
            orders.exclude(location='')
            .values('location')
            .annotate(
                total_sales=Sum('total'),
                total_orders=Count('id'),
                avg_order_value=Avg('total'),
            )
            .order_by('-total_sales')[:10]
        )

    @staticmethod
    def get_sales_operations(tenant, start_date=None, end_date=None):
        base = Order.objects.filter(tenant=tenant) if tenant else Order.objects.all()
        if start_date and end_date:
            base = base.filter(date__gte=start_date, date__lte=end_date)
        total = base.count()
        delivered = base.filter(status='delivered').count()
        cancelled = base.filter(status='cancelled').count()
        pending = base.filter(status='pending').count()
        completion_rate = (delivered / total * 100) if total > 0 else 0
        cancellation_rate = (cancelled / total * 100) if total > 0 else 0
        if start_date and end_date:
            days = (end_date - start_date).days or 1
            velocity = SalesService.get_total_sales(tenant, start_date, end_date) / days
        else:
            velocity = Decimal('0.00')
        return {
            'daily_sales_velocity': velocity,
            'completion_rate': round(completion_rate, 1),
            'cancellation_rate': round(cancellation_rate, 1),
            'pending_orders': pending,
            'total_orders': total,
        }

    @staticmethod
    def get_recent_orders(tenant, limit=50):
        qs = Order.objects.filter(tenant=tenant) if tenant else Order.objects.none()
        result = []
        for order in qs.order_by('-date')[:limit]:
            result.append({
                'id': order.id,
                'customer_name': order.customer_name,
                'customer_email': order.customer_email,
                'order_type': order.order_type,
                'order_source': order.order_source,
                'items_count': order.items.count(),
                'total': order.total,
                'status': order.status,
                'date': order.date.isoformat(),
            })
        return result
