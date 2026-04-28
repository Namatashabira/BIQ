from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils.dateparse import parse_date
from django.utils import timezone
from datetime import datetime, timedelta
from tenants.models import Tenant
from .services import SalesService
from .serializers import SalesDashboardSerializer, SalesTrendSerializer


def _resolve_tenant(request):
    user = request.user
    tenant = getattr(user, 'tenant', None)
    if not tenant:
        tenant = Tenant.objects.filter(admin=user).first()
        if tenant:
            user.tenant = tenant
            user.save(update_fields=['tenant'])
    return tenant


class SalesDashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = _resolve_tenant(request)
        if not tenant and not request.user.is_superuser:
            return Response({'error': 'No tenant found.'}, status=status.HTTP_403_FORBIDDEN)

        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        customer_type = request.query_params.get('customer_type')

        end_date = timezone.now()
        if end_date_str:
            parsed = parse_date(end_date_str)
            if parsed:
                end_date = timezone.make_aware(datetime.combine(parsed, datetime.max.time()))

        start_date = end_date - timedelta(days=30)
        if start_date_str:
            parsed = parse_date(start_date_str)
            if parsed:
                start_date = timezone.make_aware(datetime.combine(parsed, datetime.min.time()))

        if not start_date or not end_date:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

        dashboard_data = {
            'total_sales': SalesService.get_total_sales(tenant, start_date, end_date, customer_type),
            'total_orders': SalesService.get_total_orders(tenant, start_date, end_date, customer_type),
            'units_sold': SalesService.get_units_sold(tenant, start_date, end_date, customer_type),
            'average_order_value': SalesService.get_average_order_value(tenant, start_date, end_date, customer_type),
            **SalesService.get_sales_split(tenant, start_date, end_date),
            **SalesService.get_sales_growth(tenant, start_date, end_date),
            'top_products': SalesService.get_top_products(tenant, start_date, end_date),
            'customer_insights': SalesService.get_customer_insights(tenant, start_date, end_date),
            'geographic_performance': SalesService.get_geographic_performance(tenant, start_date, end_date),
            'sales_operations': SalesService.get_sales_operations(tenant, start_date, end_date),
            'recent_orders': SalesService.get_recent_orders(tenant),
        }

        serializer = SalesDashboardSerializer(dashboard_data)
        return Response(serializer.data)


class SalesTrendAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tenant = _resolve_tenant(request)
        if not tenant and not request.user.is_superuser:
            return Response({'error': 'No tenant found.'}, status=status.HTTP_403_FORBIDDEN)

        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        group_by = request.query_params.get('group_by', 'day')

        end_date = timezone.now()
        if end_date_str:
            parsed = parse_date(end_date_str)
            if parsed:
                end_date = timezone.make_aware(datetime.combine(parsed, datetime.max.time()))

        start_date = end_date - timedelta(days=30)
        if start_date_str:
            parsed = parse_date(start_date_str)
            if parsed:
                start_date = timezone.make_aware(datetime.combine(parsed, datetime.min.time()))

        if not start_date or not end_date:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

        if group_by not in ['day', 'month']:
            return Response({'error': 'group_by must be "day" or "month"'}, status=400)

        trend_data = SalesService.get_sales_trend(tenant, start_date, end_date, group_by)
        serializer = SalesTrendSerializer(trend_data, many=True)
        return Response(serializer.data)
