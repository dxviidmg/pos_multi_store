#!/bin/bash
set -e

echo "=== Aplicando migraciones ==="
python manage.py makemigrations --noinput
python manage.py migrate --noinput

echo "=== Iniciando Celery Worker ==="
celery -A pos_multi_store worker -l info &


echo "=== Iniciando Daphne ==="
exec daphne -b 0.0.0.0 -p ${PORT:-8000} pos_multi_store.asgi:application