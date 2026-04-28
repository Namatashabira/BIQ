import json
from channels.generic.websocket import AsyncWebsocketConsumer

class AdminOrdersConsumer(AsyncWebsocketConsumer):
    """Admin sees order in the admin panel in real time"""
    
    async def connect(self):
        self.group_name = "admin_orders"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def new_order(self, event):
        """Admin gets notified when user places new order"""
        await self.send(text_data=json.dumps({
            'type': 'new_order',
            'order': event['order']
        }))

class UserOrdersConsumer(AsyncWebsocketConsumer):
    """User gets notified or sees updated status in real time"""
    
    async def connect(self):
        # Get user email from URL path parameters or query params
        self.user_email = None
        
        # Try to get from URL path first (e.g., /ws/orders/user@example.com/)
        if 'email' in self.scope.get('url_route', {}).get('kwargs', {}):
            self.user_email = self.scope['url_route']['kwargs']['email']
        # Fallback to query params (e.g., ?email=user@example.com)
        elif 'email=' in self.scope['query_string'].decode():
            self.user_email = self.scope['query_string'].decode().split('email=')[1].split('&')[0]
        
        if self.user_email:
            # Sanitize email for use in group name (replace @ with _at_)
            sanitized_email = self.user_email.replace('@', '_at_').replace('.', '_')
            self.group_name = f"user_{sanitized_email}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            print(f"✅ User WebSocket connected: {self.user_email} (group: {self.group_name})")
        else:
            print("❌ User WebSocket rejected: No email provided")
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            print(f"🔌 User WebSocket disconnected: {self.user_email}")

    async def status_update(self, event):
        """User gets notified when admin updates order status"""
        print(f"📤 Sending status update to {self.user_email}: Order #{event['order_id']} -> {event['status']}")
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'order_id': event['order_id'],
            'status': event['status']
        }))
