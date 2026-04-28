from channels.generic.websocket import AsyncJsonWebsocketConsumer
from core.models import ROLE_SUPERADMIN


class ProductsConsumer(AsyncJsonWebsocketConsumer):
    global_group = "products"

    async def connect(self):
        user = self.scope.get("user")

        # Allow anonymous viewers; prefer tenant-specific when available
        self.user_role = getattr(user, "role", None) if user and user.is_authenticated else None
        self.tenant_id = None

        if user and getattr(user, "is_authenticated", False):
            if self.user_role != ROLE_SUPERADMIN:
                self.tenant_id = getattr(user, "tenant_id", None)
                memberships = getattr(user, "tenants_memberships", None)
                if self.tenant_id is None and memberships:
                    first_membership = memberships.first()
                    if first_membership:
                        self.tenant_id = first_membership.tenant_id

        # Join global group for public broadcasts
        await self.channel_layer.group_add(self.global_group, self.channel_name)

        # Join tenant-specific group when available
        if self.tenant_id:
            await self.channel_layer.group_add(f"products_tenant_{self.tenant_id}", self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.global_group, self.channel_name)
        if self.tenant_id:
            await self.channel_layer.group_discard(f"products_tenant_{self.tenant_id}", self.channel_name)

    async def products_message(self, event):
        """
        Event: {"type": "products.message", "action": "created|updated|deleted", "data": {...}}
        """
        data = event.get("data", {})
        event_tenant_id = data.get("tenant_id")

        # Superadmin gets all; tenant-scoped clients get their tenant; anonymous/global get all
        if self.user_role == ROLE_SUPERADMIN or not self.tenant_id or event_tenant_id == self.tenant_id:
            await self.send_json({
                "type": "product_event",
                "action": event.get("action"),
                "data": data,
            })
