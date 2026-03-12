web: DJANGO_SETTINGS_MODULE=estimate_site.settings_railway python init_app.py && gunicorn estimate_site.wsgi --bind 0.0.0.0:$PORT --workers 2 --threads 4 --worker-class gthread --timeout 120 --keep-alive 5 --max-requests 1000 --max-requests-jitter 50
release: DJANGO_SETTINGS_MODULE=estimate_site.settings_railway python manage.py collectstatic --noinput
