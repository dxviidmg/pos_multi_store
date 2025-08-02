import os
from celery import Celery
import ssl 

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pos_multi_store.settings")
app = Celery("pos_multi_store")

redis_url = os.environ.get("REDIS_URL") or os.environ.get("CELERY_BROKER_URL")
if redis_url and redis_url.startswith("rediss://"):
    app.conf.broker_use_ssl = {
        "ssl_cert_reqs": ssl.CERT_NONE  # o ssl.CERT_REQUIRED si el cert es válido
    }

# También para result backend si es Redis y usa rediss
result_backend_url = os.environ.get("CELERY_RESULT_BACKEND")
if result_backend_url and result_backend_url.startswith("rediss://"):
    app.conf.redis_backend_use_ssl = {
        "ssl_cert_reqs": ssl.CERT_NONE
    }
    
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()