import os

# Set the default Django settings module before importing Django/Channels components
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "admin_panel.settings")

import django
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
from core.orders import routing as order_routing
from product import routing as product_routing

# Define ASGI application with HTTP and WebSocket support
application = ProtocolTypeRouter({
    "http": get_asgi_application(),  # Standard HTTP handling
    "websocket": AuthMiddlewareStack(  # WebSocket handling with user authentication
        URLRouter(order_routing.websocket_urlpatterns + product_routing.websocket_urlpatterns)
    ),
})
