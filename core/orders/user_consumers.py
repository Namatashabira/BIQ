import json
from channels.generic.websocket import AsyncWebsocketConsumer
from urllib.parse import parse_qs

class UserNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Get user email from query parameters
        query_string = self.scope['query_string'].decode()
        query_params = parse_qs(query_string)
        
        self.user_email = query_params.get('email', [None])[0]
        
        if self.user_email:
            self.group_name = f"user_{self.user_email}"
            # Add this connection to the user-specific group
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        # Remove from group on disconnect
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle messages from frontend"""
        try:
            data = json.loads(text_data)
            # Echo back for connection testing
            await self.send(text_data=json.dumps({
                "type": "connection_test",
                "message": "Connection established",
                "user_email": self.user_email
            }))
        except json.JSONDecodeError:
            pass

    async def order_status_update(self, event):
        """Receive order status update and send to WebSocket client"""
        message = event["message"]
        await self.send(text_data=json.dumps({
            "type": "order_status_update",
            "data": message
        }))