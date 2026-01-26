web: DJANGO_SETTINGS_MODULE=estimate_site.settings_railway gunicorn estimate_site.wsgi --bind 0.0.0.0:$PORT
release: DJANGO_SETTINGS_MODULE=estimate_site.settings_railway python manage.py migrate --noinput && python manage.py collectstatic --noinput && python manage.py create_admin && python manage.py seed_modules
