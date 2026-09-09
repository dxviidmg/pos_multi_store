import os
import ssl
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pos_multi_store.settings")

app = Celery("pos_multi_store")
app.config_from_object("django.conf:settings", namespace="CELERY")

# NOTA: la alerta de "tenant sin pago tras 24h" existe como tarea Celery
# (tenants.tasks.alert_tenants_without_payment) pero su PROGRAMACIÓN está
# desactivada hasta montar beat en la infra de forma segura (un solo proceso).
# Para activarla, definir beat_schedule aquí y arrancar celery con beat:
# app.conf.beat_schedule = {
#     "alert-tenants-without-payment": {
#         "task": "tenants.tasks.alert_tenants_without_payment",
#         "schedule": 3600.0,  # cada hora
#     },
# }

redis_url = os.environ.get("REDIS_URL")

if redis_url:
    app.conf.broker_url = redis_url
    app.conf.result_backend = redis_url

    if redis_url.startswith("rediss://"):
        app.conf.broker_use_ssl = {
            "ssl_cert_reqs": ssl.CERT_NONE
        }
        app.conf.redis_backend_use_ssl = {
            "ssl_cert_reqs": ssl.CERT_NONE
        }

app.autodiscover_tasks()
