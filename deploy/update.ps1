# ==============================================================================
# HAMSVIC - Production Update Script (Windows PowerShell)
# ==============================================================================
# Usage: .\deploy\update.ps1
# 
# This script updates your production deployment.
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "🔄 HAMSVIC Production Update" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host "Started at: $(Get-Date)"
Write-Host ""

# Ensure we're in the project directory
Set-Location (Split-Path -Parent $PSScriptRoot)

# Step 1: Pull latest code from git
Write-Host "📥 Pulling latest code..." -ForegroundColor Yellow
git pull origin main

# Step 2: Build new images
Write-Host "🏗️ Building updated Docker images..." -ForegroundColor Yellow
docker-compose -f docker-compose.production.yml build --no-cache web celery celery-beat

# Step 3: Run database migrations
Write-Host "📊 Running database migrations..." -ForegroundColor Yellow
docker-compose -f docker-compose.production.yml run --rm web python manage.py migrate --noinput

# Step 4: Collect static files
Write-Host "📁 Collecting static files..." -ForegroundColor Yellow
docker-compose -f docker-compose.production.yml run --rm web python manage.py collectstatic --noinput

# Step 5: Restart services
Write-Host "🚀 Restarting services..." -ForegroundColor Yellow
docker-compose -f docker-compose.production.yml up -d --force-recreate web celery celery-beat

# Step 6: Clean up old Docker images
Write-Host "🧹 Cleaning up old images..." -ForegroundColor Yellow
docker image prune -f

# Step 7: Show status
Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "✅ Update complete!" -ForegroundColor Green
Write-Host "Finished at: $(Get-Date)"
Write-Host ""
Write-Host "📝 What was updated:" -ForegroundColor White
Write-Host "   - Latest code pulled from git"
Write-Host "   - Docker images rebuilt with all requirements"
Write-Host "   - Database migrations applied"
Write-Host "   - Static files collected"
Write-Host "   - Services restarted"
Write-Host ""
Write-Host "🔍 To check logs: docker-compose -f docker-compose.production.yml logs -f web" -ForegroundColor White
Write-Host ""

# Show container status
Write-Host "📊 Container Status:" -ForegroundColor Cyan
docker-compose -f docker-compose.production.yml ps
