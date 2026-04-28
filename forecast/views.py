from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import Business, Forecast
from .serializers import ForecastSerializer
from .services import forecast_sales
from tenants.models import Tenant
from core.business_config import BusinessConfig


def _resolve_tenant(request):
    """Resolve tenant from authenticated user."""
    user = request.user
    tenant = getattr(user, 'tenant', None)
    if not tenant:
        tenant = Tenant.objects.filter(admin=user).first()
        if tenant:
            user.tenant = tenant
            user.save(update_fields=['tenant'])
    return tenant


class MonthlyForecastView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        tenant = _resolve_tenant(request)

        # Allow tenant_uuid override only for superusers
        tenant_uuid = request.data.get("tenant_uuid")
        if tenant_uuid and request.user.is_superuser:
            try:
                tenant = Tenant.objects.get(uuid=tenant_uuid)
            except Tenant.DoesNotExist:
                return Response({"error": "Tenant not found."}, status=status.HTTP_404_NOT_FOUND)

        if not tenant:
            return Response({"error": "No tenant associated with this account."}, status=status.HTTP_403_FORBIDDEN)

        target_month = request.data.get("target_month")
        if not target_month:
            return Response({"error": "target_month is required."}, status=status.HTTP_400_BAD_REQUEST)

        business_config = BusinessConfig.objects.filter(tenant=tenant).first()
        business_type = business_config.business_type if business_config else tenant.business_type

        # Scope Business lookup strictly by tenant to prevent cross-tenant data leakage
        business, _ = Business.objects.get_or_create(
            tenant=tenant,
            defaults={'name': tenant.name, 'sector': business_type, 'owner': tenant.admin}
        )
        if business.sector != business_type:
            business.sector = business_type
            business.save(update_fields=['sector'])

        forecast_data = forecast_sales(business, business_type, int(target_month))

        forecast_obj, _ = Forecast.objects.update_or_create(
            business=business,
            target_month=target_month,
            defaults=forecast_data,
        )

        return Response(ForecastSerializer(forecast_obj).data, status=status.HTTP_200_OK)


class FinancialForecastView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        return Response({"message": "Financial forecast endpoint not yet implemented."})


class GeographicForecastView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        return Response({"message": "Geographic forecast endpoint not yet implemented."})


class RisksForecastView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        return Response({"message": "Risks forecast endpoint not yet implemented."})


class PricingForecastView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        return Response({"message": "Pricing forecast endpoint not yet implemented."})


class NinetyDayForecastView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        return Response({"message": "90 day forecast endpoint not yet implemented."})


class CustomsForecastView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        return Response({"message": "Customs forecast endpoint not yet implemented."})


class OtherForecastView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        return Response({"message": "Other forecast endpoint not yet implemented."})
