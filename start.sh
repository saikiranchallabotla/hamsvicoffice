#!/bin/bash
# Start script for Railway deployment

export DJANGO_SETTINGS_MODULE=estimate_site.settings_railway

# Default to port 8000 if PORT not set
PORT="${PORT:-8000}"

echo "Starting HAMSVIC on port $PORT..."

# Run migrations
python manage.py migrate --noinput

# Start gunicorn
exec gunicorn estimate_site.wsgi:application --bind "0.0.0.0:$PORT" --workers 2 --timeout 300
