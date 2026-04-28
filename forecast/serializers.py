# forecast/serializers.py

from rest_framework import serializers
from .models import Business, Forecast

class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = ["id", "name", "sector", "owner"]


class ForecastSerializer(serializers.ModelSerializer):
    business = BusinessSerializer(read_only=True)

    class Meta:
        model = Forecast
        fields = [
            "id",
            "business",
            "target_month",
            "baseline",
            "recent_trend",
            "sector_factor",
            "scarcity_factor",
            "universal_factor",
            "salary_factor",
            "forecast_sales",
            "restock_required",
            "restock_window",
            "sales_increase_hints",
            "summary",
            "suggested_products",
            "created_at",
        ]
