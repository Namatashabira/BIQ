from django.contrib import admin

from .models import Tenant, Worker, TenantMembership


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
	list_display = ["name", "is_verified", "created_at"]
	search_fields = ["name"]




@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
	list_display = ["tenant"]
	search_fields = ["tenant__name"]


@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
	list_display = ["user", "tenant", "role", "created_at"]
	search_fields = ["user__email", "tenant__name"]
