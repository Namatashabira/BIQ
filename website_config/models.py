
from django.db import models
from django.contrib.auth import get_user_model

# Assumes a Tenant model exists or is defined here

class Tenant(models.Model):
	name = models.CharField(max_length=100)
	api_key = models.CharField(max_length=64, unique=True)
	# Add more fields as needed (e.g., owner, created_at)
	def __str__(self):
		return self.name

# New model for allowed CORS origins per tenant
class AllowedOrigin(models.Model):
	tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='allowed_origins')
	origin = models.URLField(max_length=255)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		unique_together = ('tenant', 'origin')

	def __str__(self):
		return f"{self.origin} ({self.tenant.name})"

class OrderSyncConfig(models.Model):
	tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='order_sync_config')
	enabled = models.BooleanField(default=False)
	field_mapping = models.JSONField(default=dict, blank=True)  # {"saas_field": "website_field"}
	last_updated = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f"OrderSyncConfig for {self.tenant.name}"

class Order(models.Model):
	tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='orders')
	customer_name = models.CharField(max_length=255)
	email = models.EmailField()
	product_id = models.CharField(max_length=100)
	quantity = models.PositiveIntegerField(default=1)
	order_total = models.DecimalField(max_digits=10, decimal_places=2)
	raw_payload = models.JSONField(default=dict, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	status = models.CharField(max_length=32, default='received')  # received, error, etc.
	error_message = models.TextField(blank=True, null=True)

	def __str__(self):
		return f"Order {self.id} for {self.tenant.name}"

# Create your models here.
