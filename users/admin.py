from django.contrib import admin
from .models import UserProfile, UserTenantMembership

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__username', 'user__email', 'phone']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(UserTenantMembership)
class UserTenantMembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'tenant', 'joined_at']
    list_filter = ['tenant', 'joined_at']
    search_fields = ['user__username', 'tenant__name']
    readonly_fields = ['joined_at']