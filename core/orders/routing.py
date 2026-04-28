from django.urls import re_path
from .consumers import AdminOrdersConsumer, UserOrdersConsumer

# WebSocket URL patterns for the order workflow
websocket_urlpatterns = [
    # Admin sees order in the admin panel in real time
    re_path(r'ws/admin/orders/$', AdminOrdersConsumer.as_asgi()),
    # User gets notified or sees updated status in real time (with email in path)
    re_path(r'ws/orders/(?P<email>[^/]+)/$', UserOrdersConsumer.as_asgi()),
    # Legacy route with query param
    re_path(r'ws/user/orders/$', UserOrdersConsumer.as_asgi()),
]
