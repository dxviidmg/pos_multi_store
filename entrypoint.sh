#!/bin/bash
set -e

echo "=== Aplicando migraciones ==="
python manage.py makemigrations --noinput
python manage.py migrate --noinput

if [ "$SERVICE_TYPE" = "worker" ]; then
    echo "=== Iniciando Celery Worker ==="
    # Optimizado para Render Standard (2GB RAM, 1 CPU)
    exec celery -A pos_multi_store worker \
        -l info \
        --concurrency=2 \
        --max-memory-per-child=512000 \
        --time-limit=1800 \
        --soft-time-limit=1500
else
    echo "=== Iniciando Daphne ==="
    exec daphne -b 0.0.0.0 -p ${PORT:-8000} pos_multi_store.asgi:application
fi