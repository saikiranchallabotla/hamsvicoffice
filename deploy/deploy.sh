#!/bin/bash
# ==============================================================================
# HAMSVIC AWS DEPLOYMENT SCRIPT
# ==============================================================================
# Run this script on a fresh Ubuntu 22.04 EC2 instance
# Usage: chmod +x deploy.sh && sudo ./deploy.sh

set -e  # Exit on error

echo "=========================================="
echo "HAMSVIC AWS Deployment Script"
echo "=========================================="

# Configuration
APP_USER="ubuntu"
APP_DIR="/home/$APP_USER/hamsvic"
DOMAIN="hamsvic.com"

# ==============================================================================
# 1. SYSTEM UPDATES & DEPENDENCIES
# ==============================================================================
echo "[1/10] Updating system packages..."
apt update && apt upgrade -y

echo "[1/10] Installing dependencies..."
apt install -y \
    python3.11 python3.11-venv python3.11-dev python3-pip \
    nginx certbot python3-certbot-nginx \
    postgresql-client \
    redis-tools \
    git curl wget unzip \
    supervisor \
    libpq-dev gcc \
    tesseract-ocr poppler-utils  # For PDF OCR

# ==============================================================================
# 2. CREATE APPLICATION DIRECTORY
# ==============================================================================
echo "[2/10] Setting up application directory..."
mkdir -p $APP_DIR
mkdir -p /var/log/gunicorn
mkdir -p /var/log/celery
chown -R $APP_USER:$APP_USER $APP_DIR /var/log/gunicorn /var/log/celery

# ==============================================================================
# 3. CLONE/UPLOAD APPLICATION CODE
# ==============================================================================
echo "[3/10] Application code should be uploaded to $APP_DIR"
echo "       You can use: scp -r ./Windows\ x\ 1/* ubuntu@your-ec2:~/hamsvic/"
echo "       Or git clone from your repository"

# ==============================================================================
# 4. PYTHON VIRTUAL ENVIRONMENT
# ==============================================================================
echo "[4/10] Creating Python virtual environment..."
cd $APP_DIR
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

# ==============================================================================
# 5. ENVIRONMENT CONFIGURATION
# ==============================================================================
echo "[5/10] Setting up environment..."
if [ ! -f "$APP_DIR/.env" ]; then
    echo "ERROR: .env file not found!"
    echo "Copy .env.production.example to .env and fill in the values"
    exit 1
fi

# ==============================================================================
# 6. DATABASE MIGRATIONS
# ==============================================================================
echo "[6/10] Running database migrations..."
source venv/bin/activate
python manage.py migrate --no-input
python manage.py collectstatic --no-input

# ==============================================================================
# 7. SYSTEMD SERVICES
# ==============================================================================
echo "[7/10] Setting up systemd services..."
cp deploy/hamsvic.service /etc/systemd/system/
cp deploy/hamsvic-celery.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable hamsvic
systemctl enable hamsvic-celery
systemctl start hamsvic
systemctl start hamsvic-celery

# ==============================================================================
# 8. NGINX CONFIGURATION
# ==============================================================================
echo "[8/10] Configuring Nginx..."
cp deploy/nginx.conf /etc/nginx/sites-available/hamsvic
ln -sf /etc/nginx/sites-available/hamsvic /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

# ==============================================================================
# 9. SSL CERTIFICATE (Let's Encrypt)
# ==============================================================================
echo "[9/10] Setting up SSL certificate..."
certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos -m admin@$DOMAIN

# ==============================================================================
# 10. FIREWALL
# ==============================================================================
echo "[10/10] Configuring firewall..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "=========================================="
echo "DEPLOYMENT COMPLETE!"
echo "=========================================="
echo ""
echo "Your application should now be running at:"
echo "  https://$DOMAIN"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status hamsvic"
echo "  sudo systemctl restart hamsvic"
echo "  sudo journalctl -u hamsvic -f"
echo "  sudo tail -f /var/log/nginx/hamsvic_error.log"
echo ""
