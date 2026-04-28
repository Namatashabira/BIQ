from django.contrib import admin
from .models import Order, OrderItem

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer_name", "customer_email", "status", "total", "date")
    list_filter = ("status", "delivery", "date")
    search_fields = ("customer_name", "customer_email")

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "product_name", "quantity", "price")
    search_fields = ("product_name",)
