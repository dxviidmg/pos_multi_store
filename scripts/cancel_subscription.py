"""
Cancela una suscripción específica en Mercado Pago y actualiza el status local.

Uso: python manage.py runscript cancel_subscriptions
"""
import requests
from django.conf import settings
from tenants.models import Subscription


def run():
    mp_id = input("Ingresa el mp_subscription_id: ").strip()
    if not mp_id:
        print("No se proporcionó un ID.")
        return

    mp_access_token = settings.MERCADO_PAGO_ACCESS_TOKEN
    headers = {
        "Authorization": f"Bearer {mp_access_token}",
        "Content-Type": "application/json",
    }

    response = requests.put(
        f"https://api.mercadopago.com/preapproval/{mp_id}",
        json={"status": "cancelled"},
        headers=headers,
    )

    if response.status_code == 200:
        print(f"✓ Cancelada en MP: {mp_id}")
        updated = Subscription.objects.filter(mp_subscription_id=mp_id).update(status="cancelled")
        if updated:
            print("✓ Status local actualizado a 'cancelled'")
        else:
            print("⚠ No se encontró suscripción local con ese ID")
    else:
        print(f"✗ Error MP: {response.status_code} - {response.text}")
