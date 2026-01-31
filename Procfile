web: DJANGO_SETTINGS_MODULE=estimate_site.settings_railway python init_app.py && gunicorn estimate_site.wsgi --bind 0.0.0.0:$PORT
release: DJANGO_SETTINGS_MODULE=estimate_site.settings_railway python manage.py collectstatic --noinput
