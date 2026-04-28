from django.apps import AppConfig

class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.orders'
    
    def ready(self):
        # Import signals when app is ready
        try:
            from . import signals
        except ImportError:
            pass