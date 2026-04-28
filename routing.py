from core.orders.routing import websocket_urlpatterns as order_patterns
from product.routing import websocket_urlpatterns as product_patterns

# Main WebSocket URL patterns - combine all WebSocket routes
websocket_urlpatterns = order_patterns + product_patterns