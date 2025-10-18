#!/bin/bash
set -e

echo "=== Aplicando migraciones ==="
python manage.py makemigrations --noinput
python manage.py migrate --noinput

echo "=== Iniciando Celery Worker ==="
celery -A pos_multi_store worker -l info &


echo "=== Iniciando Gunicorn ==="
exec gunicorn pos_multi_store.wsgi:application --timeout 120 --workers 4 --threads 2