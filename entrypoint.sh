#!/bin/bash
set -e

echo "=== Aplicando migraciones ==="
python manage.py makemigrations --noinput || true
python manage.py migrate --noinput

case "$SERVICE_TYPE" in
  web)
    echo "=== Iniciando Gunicorn (web) ==="
    exec gunicorn pos_multi_store.wsgi:application --timeout 120 --workers 4 --threads 2
    ;;
  worker)
    echo "=== Iniciando Celery Worker ==="
    exec celery -A pos_multi_store worker --loglevel=info
    ;;
  beat)
    echo "=== Iniciando Celery Beat ==="
    exec celery -A pos_multi_store beat --loglevel=info
    ;;
  *)
    echo "Error: SERVICE_TYPE debe ser 'web', 'worker' o 'beat'"
    exit 1
    ;;
esac