web: gunicorn estimate_site.wsgi --bind 0.0.0.0:${PORT:-8000}
release: python manage.py migrate --noinput && python manage.py collectstatic --noinput
