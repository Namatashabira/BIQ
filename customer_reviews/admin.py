from django.contrib import admin
from .models import CustomerReview

@admin.register(CustomerReview)
class CustomerReviewAdmin(admin.ModelAdmin):
    list_display = ('product_id', 'product_name', 'rating', 'created_at', 'user_ip')
    search_fields = ('product_id', 'product_name', 'feedback', 'product_details')
    list_filter = ('rating', 'created_at')
