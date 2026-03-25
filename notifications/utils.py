from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def notify_store(store, tenant_id, data):
    """Envía notificación al grupo de la tienda y al grupo del tenant (owner fuera de tienda).
    store: instancia de Store
    """
    data['store_id'] = store.id
    data['store_name'] = store.name
    channel_layer = get_channel_layer()
    send = async_to_sync(channel_layer.group_send)
    msg = {'type': 'notification', 'data': data}
    send(f'store_{store.id}', msg)
    send(f'tenant_{tenant_id}', msg)
