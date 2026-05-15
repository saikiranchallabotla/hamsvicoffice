#!/bin/bash
# =============================================================================
# Quick re-deploy script (for subsequent deployments after initial setup)
# Run: bash redeploy.sh
# =============================================================================
set -e

APP_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$APP_DIR"

echo "Pulling latest code..."
git pull origin main

echo "Activating venv..."
[ -d "venv" ] && source venv/bin/activate
[ -d ".venv" ] && source .venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt --quiet

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Restarting Gunicorn..."
sudo systemctl restart gunicorn

echo "Done! Site updated."
