from django.db import models
from tenants.models import Tenant


class CustomerReview(models.Model):

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True, related_name='customer_reviews', db_index=True)
    product_id = models.CharField(max_length=100)
    product_name = models.CharField(max_length=255)
    product_details = models.TextField(blank=True)
    rating = models.PositiveSmallIntegerField()
    feedback = models.TextField(blank=True)
    reviewer_name = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    user_ip = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"Review for {self.product_name} ({self.product_id}) - {self.rating} stars"
