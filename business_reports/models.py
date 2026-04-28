
from django.db import models

class SavedBusinessReport(models.Model):
	tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='business_reports')
	created_at = models.DateTimeField(auto_now_add=True)
	data = models.JSONField()
	# Optionally, you can add a name, user, or period fields
	name = models.CharField(max_length=255, blank=True, null=True)
	start_date = models.DateField(blank=True, null=True)
	end_date = models.DateField(blank=True, null=True)

	def __str__(self):
		return f"Business Report for {self.tenant} at {self.created_at:%Y-%m-%d %H:%M}" 
