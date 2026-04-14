import os
import ssl
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pos_multi_store.settings")

app = Celery("pos_multi_store")
app.config_from_object("django.conf:settings", namespace="CELERY")

redis_url = os.environ.get("REDIS_URL")

if redis_url:
    app.conf.broker_url = redis_url
    app.conf.result_backend = redis_url

    if redis_url.startswith("rediss://"):
        # Upstash uses valid SSL certificates
        app.conf.broker_use_ssl = {
            "ssl_cert_reqs": ssl.CERT_REQUIRED,
            "ssl_check_hostname": True
        }
        app.conf.redis_backend_use_ssl = {
            "ssl_cert_reqs": ssl.CERT_REQUIRED,
            "ssl_check_hostname": True
        }

app.autodiscover_tasks()