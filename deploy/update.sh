#!/bin/bash
# ==============================================================================
# HAMSVIC - Production Update Script
# ==============================================================================
# Usage: ./deploy/update.sh
# 
# This script updates your production deployment with zero to minimal downtime.
# It pulls the latest code, rebuilds containers, and restarts services.
# ==============================================================================

set -e

echo "🔄 HAMSVIC Production Update"
echo "================================"
echo "Started at: $(date)"
echo ""

# Ensure we're in the project directory
cd "$(dirname "$0")/.."

# Step 1: Pull latest code from git
echo "📥 Pulling latest code..."
git pull origin main

# Step 2: Check if requirements changed
echo "📦 Checking for dependency changes..."
REQUIREMENTS_CHANGED=$(git diff HEAD~1 --name-only | grep -c "requirements.txt" || true)

# Step 3: Backup database before update
echo "💾 Creating database backup..."
BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"
docker-compose -f docker-compose.production.yml exec -T postgres pg_dump -U ${DB_USER:-hamsvic} ${DB_NAME:-hamsvic_production} > "backups/$BACKUP_FILE" 2>/dev/null || echo "⚠️ Database backup skipped (no existing database or first deploy)"

# Step 4: Build new images (if requirements changed, this will include new packages)
echo "🏗️ Building updated Docker images..."
docker-compose -f docker-compose.production.yml build --no-cache web celery celery-beat

# Step 5: Run database migrations
echo "📊 Running database migrations..."
docker-compose -f docker-compose.production.yml run --rm web python manage.py migrate --noinput

# Step 6: Collect static files
echo "📁 Collecting static files..."
docker-compose -f docker-compose.production.yml run --rm web python manage.py collectstatic --noinput

# Step 7: Restart services with minimal downtime
echo "🚀 Restarting services..."
docker-compose -f docker-compose.production.yml up -d --force-recreate web celery celery-beat

# Step 8: Clean up old Docker images
echo "🧹 Cleaning up old images..."
docker image prune -f

# Step 9: Verify deployment
echo "✅ Verifying deployment..."
sleep 5
HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health/ || echo "000")
if [ "$HEALTH_CHECK" = "200" ]; then
    echo "✅ Health check passed!"
else
    echo "⚠️ Health check returned: $HEALTH_CHECK"
    echo "   Checking container logs..."
    docker-compose -f docker-compose.production.yml logs --tail=20 web
fi

echo ""
echo "================================"
echo "✅ Update complete!"
echo "Finished at: $(date)"
echo ""
echo "📝 What was updated:"
echo "   - Latest code pulled from git"
echo "   - Docker images rebuilt with all requirements"
echo "   - Database migrations applied"
echo "   - Static files collected"
echo "   - Services restarted"
echo ""
echo "🔍 To check logs: docker-compose -f docker-compose.production.yml logs -f web"
