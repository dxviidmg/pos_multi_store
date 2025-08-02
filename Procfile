release: python manage.py makemigrations
release: python manage.py migrate
web: gunicorn pos_multi_store.wsgi
worker: celery -A pos_multi_store worker --loglevel=info