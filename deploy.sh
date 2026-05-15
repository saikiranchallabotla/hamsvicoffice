#!/bin/bash
# =============================================================================
# Hamsvic Office - EC2 Deployment Script
# Run this on your EC2 instance: bash deploy.sh
# =============================================================================
set -e

APP_DIR=$(cd "$(dirname "$0")" && pwd)
DOMAIN="hamsvic.com"
APP_USER=$(whoami)

echo "========================================="
echo "  Hamsvic Office - Deployment"
echo "========================================="
echo "App directory: $APP_DIR"
echo "Domain: $DOMAIN"
echo "User: $APP_USER"
echo ""

# ----- Step 1: Pull latest code -----
echo "[1/7] Pulling latest code..."
cd "$APP_DIR"
git pull origin main

# ----- Step 2: Install dependencies -----
echo "[2/7] Installing Python dependencies..."
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
fi
pip install -r requirements.txt --quiet

# ----- Step 3: Run migrations -----
echo "[3/7] Running database migrations..."
python manage.py migrate --noinput

# ----- Step 4: Collect static files -----
echo "[4/7] Collecting static files..."
python manage.py collectstatic --noinput --clear 2>/dev/null || python manage.py collectstatic --noinput

# ----- Step 5: Setup Nginx (if not already configured) -----
echo "[5/7] Configuring Nginx..."
if ! command -v nginx &>/dev/null; then
    echo "Installing Nginx..."
    sudo apt update -qq
    sudo apt install -y nginx
fi

# Create Nginx config for the site
sudo tee /etc/nginx/sites-available/hamsvic > /dev/null <<'NGINX'
server {
    listen 80;
    server_name hamsvic.com www.hamsvic.com;

    # Max upload size (for Excel files etc.)
    client_max_body_size 20M;

    # Static files - served directly by Nginx
    location /static/ {
        alias APP_DIR_PLACEHOLDER/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media files
    location /media/ {
        alias APP_DIR_PLACEHOLDER/media/;
        expires 7d;
    }

    # Proxy to Gunicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
    }
}
NGINX

# Replace placeholder with actual app directory
sudo sed -i "s|APP_DIR_PLACEHOLDER|$APP_DIR|g" /etc/nginx/sites-available/hamsvic

# Enable the site
sudo ln -sf /etc/nginx/sites-available/hamsvic /etc/nginx/sites-enabled/hamsvic
sudo rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true

# Test and reload Nginx
sudo nginx -t && sudo systemctl reload nginx
echo "Nginx configured."

# ----- Step 6: Setup Gunicorn service -----
echo "[6/7] Configuring Gunicorn service..."
VENV_PATH="$APP_DIR/venv"
[ -d "$APP_DIR/.venv" ] && VENV_PATH="$APP_DIR/.venv"

sudo tee /etc/systemd/system/gunicorn.service > /dev/null <<EOF
[Unit]
Description=Hamsvic Gunicorn Daemon
After=network.target

[Service]
User=$APP_USER
Group=www-data
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_PATH/bin/gunicorn estimate_site.wsgi:application \\
    --bind 127.0.0.1:8000 \\
    --workers 3 \\
    --timeout 120 \\
    --access-logfile - \\
    --error-logfile -
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable gunicorn
sudo systemctl restart gunicorn
echo "Gunicorn started."

# ----- Step 7: SSL with Certbot -----
echo "[7/7] Setting up HTTPS with Let's Encrypt..."
if ! command -v certbot &>/dev/null; then
    echo "Installing Certbot..."
    sudo apt update -qq
    sudo apt install -y certbot python3-certbot-nginx
fi

# Check if cert already exists
if sudo certbot certificates 2>/dev/null | grep -q "$DOMAIN"; then
    echo "SSL certificate already exists. Renewing if needed..."
    sudo certbot renew --quiet
else
    echo ""
    echo "========================================="
    echo "  IMPORTANT: SSL Certificate Setup"
    echo "========================================="
    echo "Make sure your DNS is pointing to this server before proceeding!"
    echo ""
    read -p "Proceed with SSL setup? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos --redirect --email admin@$DOMAIN || {
            echo ""
            echo "Certbot failed. You can run it manually later:"
            echo "  sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN"
        }
    else
        echo "Skipping SSL. Run later: sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN"
    fi
fi

# ----- Done -----
echo ""
echo "========================================="
echo "  Deployment Complete!"
echo "========================================="
echo ""
echo "Check status:"
echo "  sudo systemctl status gunicorn"
echo "  sudo systemctl status nginx"
echo "  curl -I https://$DOMAIN"
echo ""
echo "View logs:"
echo "  sudo journalctl -u gunicorn -f"
echo "  sudo tail -f /var/log/nginx/error.log"
echo ""
