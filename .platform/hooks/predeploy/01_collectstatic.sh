#!/bin/bash
source /var/app/venv/*/bin/activate
cd /var/app/current

# Create logs directory if needed (for any file-based logging)
mkdir -p /var/app/current/logs

# Collect static files
python manage.py collectstatic --noinput
