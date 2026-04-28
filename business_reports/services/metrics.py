from django.db.models import Sum, Count, Avg
from django.utils.timezone import now

from core.orders.models import Order, OrderItem
from product.models import Product
from accounting.models import Expense, Tax


class ReportMetricsService:
    """
    Collects and aggregates raw data from existing apps, scoped by tenant.
    Read-only.
    """

    @staticmethod
    def _order_qs(start_date, end_date, tenant):
        qs = Order.objects.filter(tenant=tenant)
        if start_date and end_date:
            qs = qs.filter(date__range=[start_date, end_date])
        return qs

    @staticmethod
    def sales_metrics(start_date, end_date, tenant):
        qs = ReportMetricsService._order_qs(start_date, end_date, tenant).filter(
            status__in=['confirmed', 'delivered']
        )
        total_sales = qs.aggregate(total=Sum('total'))['total'] or 0
        total_orders = qs.count()
        top_products = (
            OrderItem.objects.filter(order__in=qs)
            .values('product_name')
            .annotate(revenue=Sum('price'), qty=Sum('quantity'))
            .order_by('-revenue')[:5]
        )
        monthly = []
        for i in range(6):
            from datetime import timedelta
            ref = now().replace(day=1) - timedelta(days=30 * i)
            m_end = ref + timedelta(days=30)
            m_qs = qs.filter(date__range=[ref.date(), m_end.date()])
            monthly.append({
                'month': ref.strftime('%b %Y'),
                'revenue': float(m_qs.aggregate(Sum('total'))['total__sum'] or 0),
                'orders': m_qs.count(),
            })

        return {
            'total_sales': float(total_sales),
            'total_orders': total_orders,
            'average_order_value': float(total_sales / total_orders) if total_orders else 0,
            'top_products': list(top_products),
            'monthly_trends': list(reversed(monthly)),
        }

    @staticmethod
    def expense_metrics(start_date, end_date, tenant):
        try:
            qs = Expense.objects.filter(tenant=tenant)
            if start_date and end_date:
                qs = qs.filter(date__range=[start_date, end_date])
            total = qs.aggregate(total=Sum('amount'))['total'] or 0
            breakdown = list(
                qs.values('category').annotate(total=Sum('amount')).order_by('-total')
            )
        except Exception:
            total = 0
            breakdown = []
        return {'total_expenses': float(total), 'breakdown': breakdown}

    @staticmethod
    def tax_metrics(start_date, end_date, tenant):
        try:
            qs = Tax.objects.filter(tenant=tenant)
            if start_date and end_date:
                qs = qs.filter(period_start__gte=start_date, period_end__lte=end_date)
            vat = qs.filter(tax_type='vat').aggregate(total=Sum('amount'))['total'] or 0
        except Exception:
            vat = 0
        return {'vat_collected': float(vat)}

    @staticmethod
    def order_metrics(start_date, end_date, tenant):
        qs = ReportMetricsService._order_qs(start_date, end_date, tenant)
        total = qs.count()
        fulfilled = qs.filter(status__in=['delivered', 'confirmed']).count()
        status_dist = {
            item['status']: item['count']
            for item in qs.values('status').annotate(count=Count('id'))
        }
        return {
            'total_orders': total,
            'fulfilled_orders': fulfilled,
            'fulfillment_rate': round((fulfilled / total) * 100, 2) if total else 0,
            'status_distribution': status_dist,
        }

    @staticmethod
    def inventory_metrics(tenant):
        try:
            qs = Product.objects.filter(tenant=tenant)
            low_stock = list(qs.filter(stock__lte=5).values('name', 'stock'))
            total_value = qs.aggregate(val=Sum('retail_price'))['val'] or 0
            return {
                'low_stock_items': low_stock,
                'total_stock_items': qs.count(),
                'total_value': float(total_value),
            }
        except Exception:
            return {'low_stock_items': [], 'total_stock_items': 0, 'total_value': 0}
