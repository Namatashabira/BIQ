# forecast/models.py

from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()

class Business(models.Model):
    """Business profile — one per tenant"""
    name = models.CharField(max_length=255)
    sector = models.CharField(max_length=50)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="businesses")
    tenant = models.OneToOneField(
        'tenants.Tenant', on_delete=models.CASCADE, related_name='business', null=True, blank=True
    )

    def __str__(self):
        return self.name


class Forecast(models.Model):
    """Stores monthly forecast for a business"""
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="forecasts")
    target_month = models.PositiveSmallIntegerField()  # 1=Jan, 12=Dec
    baseline = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    recent_trend = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    sector_factor = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("1.00"))
    scarcity_factor = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("1.00"))
    universal_factor = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("1.00"))
    salary_factor = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("1.00"))
    forecast_sales = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    restock_required = models.BooleanField(default=False)
    restock_window = models.CharField(max_length=100, null=True, blank=True)
    sales_increase_hints = models.JSONField(default=list, blank=True)
    summary = models.TextField(blank=True)
    suggested_products = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("business", "target_month")
        ordering = ["business", "target_month"]

    def __str__(self):
        return f"{self.business.name} - Month {self.target_month}"
