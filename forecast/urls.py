# forecast/urls.py

from django.urls import path

from .views import (
    MonthlyForecastView,
    FinancialForecastView,
    GeographicForecastView,
    RisksForecastView,
    PricingForecastView,
    NinetyDayForecastView,
    CustomsForecastView,
    OtherForecastView,
)

urlpatterns = [
    path("forecast/", MonthlyForecastView.as_view(), name="monthly-forecast"),
    path("forecast/financial/", FinancialForecastView.as_view(), name="financial-forecast"),
    path("forecast/geographic/", GeographicForecastView.as_view(), name="geographic-forecast"),
    path("forecast/risks/", RisksForecastView.as_view(), name="risks-forecast"),
    path("forecast/pricing/", PricingForecastView.as_view(), name="pricing-forecast"),
    path("forecast/90days/", NinetyDayForecastView.as_view(), name="90day-forecast"),
    path("forecast/customs/", CustomsForecastView.as_view(), name="customs-forecast"),
    path("forecast/other/", OtherForecastView.as_view(), name="other-forecast"),
]
