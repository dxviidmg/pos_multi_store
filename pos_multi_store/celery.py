import os
import ssl
import django
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pos_multi_store.settings")

django.setup()

app = Celery("pos_multi_store")
app.config_from_object("django.conf:settings", namespace="CELERY")

redis_url = os.environ.get("REDIS_CELERY_URL") or os.environ.get("REDIS_URL")

if redis_url:
    app.conf.broker_url = redis_url
    app.conf.result_backend = redis_url

    if redis_url.startswith("rediss://"):
        ssl_config = {
            "ssl_cert_reqs": ssl.CERT_NONE,
            "ssl_check_hostname": False,
        }

        app.conf.broker_use_ssl = ssl_config
        app.conf.redis_backend_use_ssl = ssl_config

app.autodiscover_tasks()