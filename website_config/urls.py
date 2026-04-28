from django.urls import path
from .views import OrderSyncConfigView, IncomingOrderView, OrderSyncTestView, OrderLogsView, AllowedOriginListCreateView, AllowedOriginDeleteView

urlpatterns = [
    path('config/', OrderSyncConfigView.as_view(), name='order_sync_config'),
    path('orders/incoming/', IncomingOrderView.as_view(), name='incoming_order'),
    path('orders/test/', OrderSyncTestView.as_view(), name='order_sync_test'),
    path('orders/logs/', OrderLogsView.as_view(), name='order_logs'),
    path('allowed-origins/', AllowedOriginListCreateView.as_view(), name='allowed_origin_list_create'),
    path('allowed-origins/<int:pk>/', AllowedOriginDeleteView.as_view(), name='allowed_origin_delete'),
]
