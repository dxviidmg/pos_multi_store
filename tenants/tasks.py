from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from core.services.email import email_service
from .models import Tenant, Payment


@shared_task
def alert_tenants_without_payment(hours=24):
    """
    Envía a soporte una alerta por cada tenant registrado hace más de `hours`
    que aún no tiene ningún Payment y al que no se le ha enviado la alerta.
    Manda UNA sola alerta por tenant (marca no_payment_alert_sent_at).
    """
    cutoff = timezone.now() - timedelta(hours=hours)
    candidates = Tenant.objects.filter(
        created_at__lte=cutoff,
        is_sandbox=False,
        no_payment_alert_sent_at__isnull=True,
    )

    alerted = 0
    for tenant in candidates:
        if Payment.objects.filter(tenant=tenant).exists():
            continue
        email_service.notify_tenant_without_payment(tenant, hours=hours)
        tenant.no_payment_alert_sent_at = timezone.now()
        tenant.save(update_fields=["no_payment_alert_sent_at"])
        alerted += 1

    return f"alertas enviadas: {alerted}"
