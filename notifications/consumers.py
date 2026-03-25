import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from rest_framework.authtoken.models import Token


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        query = self.scope['query_string'].decode()
        params = dict(p.split('=') for p in query.split('&') if '=' in p)
        token_key = params.get('token')
        store_id = params.get('store_id')

        user_data = await self.get_user_data(token_key)
        if not user_data:
            await self.close()
            return

        self.groups_to_join = []
        tenant_id, role, user_store_id = user_data

        if role == 'owner' and not store_id:
            # Owner fuera de tienda: recibe de todas
            self.groups_to_join.append(f'tenant_{tenant_id}')
        elif role == 'owner' and store_id:
            # Owner dentro de una tienda: solo esa tienda
            self.groups_to_join.append(f'store_{store_id}')
        else:
            # Manager/Seller: su tienda
            self.groups_to_join.append(f'store_{user_store_id}')

        for group in self.groups_to_join:
            await self.channel_layer.group_add(group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        for group in getattr(self, 'groups_to_join', []):
            await self.channel_layer.group_discard(group, self.channel_name)

    async def notification(self, event):
        await self.send(text_data=json.dumps(event['data']))

    @database_sync_to_async
    def get_user_data(self, token_key):
        try:
            user = Token.objects.select_related('user').get(key=token_key).user
            tenant = user.get_tenant()
            role = user.get_role()
            store = user.get_store()
            return tenant.id, role, store.id if store else None
        except Token.DoesNotExist:
            return None
