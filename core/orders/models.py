# Import models from core.models to avoid duplication
from core.models import Order, OrderItem

# Re-export for convenience
__all__ = ['Order', 'OrderItem']
