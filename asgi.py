"""
ASGI config for admin_panel project.
"""

import os
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from routing import websocket_urlpatterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "admin_panel.settings")

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})
