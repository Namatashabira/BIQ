from django.urls import path
from django.http import JsonResponse
from .views import UserOrderView, AdminOrderView, order_status_page, place_order


def health_check(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path('health/', health_check, name='health-check'),

    # User places an order on the frontend
    path('user/orders/', UserOrderView.as_view(), name='user-orders'),
    
    # Alternative place-order endpoint using @api_view
    path('place-order/', place_order, name='place-order'),
    
    # Admin sees order in the admin panel & updates status
    path('orders/', AdminOrderView.as_view(), name='admin-orders'),
    
    # Order status page for users
    path('order-status/', order_status_page, name='order-status-page'),
]
