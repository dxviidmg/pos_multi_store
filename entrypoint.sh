#!/bin/bash
set -e

echo "=== Aplicando migraciones ==="
python manage.py makemigrations --noinput
python manage.py migrate --noinput

echo "=== Iniciando Celery Worker en background ==="
celery -A pos_multi_store worker \
    -l info \
    --concurrency=2 \
    --max-memory-per-child=512000 \
    --time-limit=1800 \
    --soft-time-limit=1500 &
CELERY_PID=$!

echo "=== Iniciando Daphne ==="
daphne -b 0.0.0.0 -p ${PORT:-8000} pos_multi_store.asgi:application

kill $CELERY_PID
