#!/bin/bash
set -e

echo "=== Aplicando migraciones ==="
python manage.py makemigrations --noinput
python manage.py migrate --noinput

if [ "$SERVICE_TYPE" = "worker" ]; then
    echo "=== Iniciando Celery Worker ==="
    exec celery -A pos_multi_store worker -l info --concurrency=4
else
    echo "=== Iniciando Daphne ==="
    exec daphne -b 0.0.0.0 -p ${PORT:-8000} pos_multi_store.asgi:application
fi
