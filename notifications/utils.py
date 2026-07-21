import logging

from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


async def notify_store(store, tenant_id, data):
    """Envía notificación al grupo de la tienda y al grupo del tenant (owner fuera de tienda).
    store: instancia de Store
    No interrumpe la operación si Redis no está disponible.
    """
    try:
        data['store_id'] = store.id
        data['store_name'] = store.name
        channel_layer = get_channel_layer()
        msg = {'type': 'notification', 'data': data}
        await channel_layer.group_send(f'store_{store.id}', msg)
        await channel_layer.group_send(f'tenant_{tenant_id}', msg)
    except Exception as e:
        logger.warning(f"Notification failed (Redis unavailable?): {e}")
