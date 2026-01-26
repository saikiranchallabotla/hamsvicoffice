#!/bin/bash
# ==============================================================================
# HAMSVIC - Docker Production Deployment Script
# ==============================================================================
# Usage: ./deploy/docker-deploy.sh [domain] [email]
# Example: ./deploy/docker-deploy.sh hamsvic.com admin@hamsvic.com
# ==============================================================================

set -e

DOMAIN=${1:-"localhost"}
EMAIL=${2:-"admin@example.com"}

echo "🚀 HAMSVIC Docker Deployment"
echo "================================"
echo "Domain: $DOMAIN"
echo "Email: $EMAIL"
echo ""

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ ERROR: .env file not found!"
    echo "Please copy .env.production.example to .env and fill in the values:"
    echo "  cp .env.production.example .env"
    echo "  nano .env"
    exit 1
fi

# Generate SECRET_KEY if not set
if ! grep -q "SECRET_KEY=" .env || grep -q "SECRET_KEY=$" .env; then
    SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')
    sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" .env
    echo "✅ Generated new SECRET_KEY"
fi

# Update domain in .env
sed -i "s/ALLOWED_HOSTS=.*/ALLOWED_HOSTS=$DOMAIN,www.$DOMAIN/" .env
sed -i "s/PRIMARY_DOMAIN=.*/PRIMARY_DOMAIN=$DOMAIN/" .env

echo "📦 Building Docker images..."
docker-compose -f docker-compose.production.yml build

echo "🗄️ Starting database and redis..."
docker-compose -f docker-compose.production.yml up -d postgres redis
sleep 10

echo "📊 Running migrations..."
docker-compose -f docker-compose.production.yml run --rm web python manage.py migrate

echo "📁 Collecting static files..."
docker-compose -f docker-compose.production.yml run --rm web python manage.py collectstatic --noinput

# Start nginx without SSL first (for Let's Encrypt verification)
echo "🌐 Starting nginx..."
docker-compose -f docker-compose.production.yml up -d nginx

# Get SSL certificate if not localhost
if [ "$DOMAIN" != "localhost" ]; then
    echo "🔒 Getting SSL certificate..."
    docker-compose -f docker-compose.production.yml run --rm certbot certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        --email $EMAIL \
        --agree-tos \
        --no-eff-email \
        -d $DOMAIN \
        -d www.$DOMAIN
fi

echo "🚀 Starting all services..."
docker-compose -f docker-compose.production.yml up -d

echo ""
echo "✅ Deployment complete!"
echo "================================"
echo "Your site is now available at:"
if [ "$DOMAIN" != "localhost" ]; then
    echo "  https://$DOMAIN"
else
    echo "  http://localhost"
fi
echo ""
echo "Useful commands:"
echo "  View logs: docker-compose -f docker-compose.production.yml logs -f"
echo "  Stop: docker-compose -f docker-compose.production.yml down"
echo "  Restart: docker-compose -f docker-compose.production.yml restart"
echo "  Shell: docker-compose -f docker-compose.production.yml exec web python manage.py shell"
