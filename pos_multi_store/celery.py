import os
import ssl
from celery import Celery
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pos_multi_store.settings")

app = Celery("pos_multi_store")
app.config_from_object("django.conf:settings", namespace="CELERY")

redis_url = settings.REDIS_URL

if redis_url and redis_url.startswith("rediss://"):
    app.conf.broker_use_ssl = {
        "ssl_cert_reqs": ssl.CERT_REQUIRED,
        "ssl_check_hostname": True
    }
    app.conf.redis_backend_use_ssl = {
        "ssl_cert_reqs": ssl.CERT_REQUIRED,
        "ssl_check_hostname": True
    }

app.autodiscover_tasks()