# HAMSVIC - Deployment & Update Guide

## 🚀 First-Time Deployment

### Prerequisites
1. Docker & Docker Compose installed
2. Git installed
3. Domain pointed to your server (optional for HTTPS)

### Steps

```bash
# 1. Clone the repository
git clone https://your-repo-url.git
cd hamsvic

# 2. Create environment file
cp .env.production.example .env
# Edit .env with your values (database password, secret key, etc.)

# 3. Deploy
chmod +x deploy/docker-deploy.sh
./deploy/docker-deploy.sh yourdomain.com admin@yourdomain.com
```

---

## 🔄 Updating Production (After Making Changes)

### Method 1: Using Update Script (Recommended)

**Linux/Mac:**
```bash
chmod +x deploy/update.sh
./deploy/update.sh
```

**Windows PowerShell:**
```powershell
.\deploy\update.ps1
```

### Method 2: Manual Update

```bash
# Pull latest code
git pull origin main

# Rebuild containers (includes all requirements.txt packages)
docker-compose -f docker-compose.production.yml build --no-cache web

# Run migrations
docker-compose -f docker-compose.production.yml run --rm web python manage.py migrate

# Collect static files
docker-compose -f docker-compose.production.yml run --rm web python manage.py collectstatic --noinput

# Restart services
docker-compose -f docker-compose.production.yml up -d --force-recreate web celery celery-beat
```

---

## ⏱️ Update Timeline for Users

| Change Type | User Sees Update | Downtime |
|-------------|------------------|----------|
| Python/Django code | Immediately after restart | ~10-30 seconds |
| HTML Templates | Immediately after restart | ~10-30 seconds |
| CSS/JavaScript | After cache expires or hard refresh | None |
| Database schema | Immediately after migrate | None |
| New Python packages | After Docker rebuild | ~1-2 minutes |

---

## 📦 Adding New Python Packages

1. Add the package to `requirements.txt`:
   ```
   new-package==1.2.3
   ```

2. Rebuild Docker image:
   ```bash
   docker-compose -f docker-compose.production.yml build --no-cache web
   ```

3. Restart services:
   ```bash
   docker-compose -f docker-compose.production.yml up -d --force-recreate web
   ```

---

## 🔍 Monitoring & Logs

```bash
# View all container logs
docker-compose -f docker-compose.production.yml logs -f

# View only web server logs
docker-compose -f docker-compose.production.yml logs -f web

# Check container status
docker-compose -f docker-compose.production.yml ps

# Check health
curl http://localhost:8000/health/
```

---

## 🛠️ Common Commands

```bash
# Stop all services
docker-compose -f docker-compose.production.yml down

# Start all services
docker-compose -f docker-compose.production.yml up -d

# Restart specific service
docker-compose -f docker-compose.production.yml restart web

# Run Django shell
docker-compose -f docker-compose.production.yml exec web python manage.py shell

# Create superuser
docker-compose -f docker-compose.production.yml exec web python manage.py createsuperuser

# Database backup
docker-compose -f docker-compose.production.yml exec postgres pg_dump -U hamsvic hamsvic_production > backup.sql

# Database restore
docker-compose -f docker-compose.production.yml exec -T postgres psql -U hamsvic hamsvic_production < backup.sql
```

---

## 🔒 Zero-Downtime Deployment (Advanced)

For zero-downtime updates, use rolling restart:

```bash
# Scale up to 2 instances
docker-compose -f docker-compose.production.yml up -d --scale web=2

# Wait for new instance to be healthy
sleep 30

# Scale back down (removes old instance)
docker-compose -f docker-compose.production.yml up -d --scale web=1
```

---

## ⚠️ Troubleshooting

### Container won't start
```bash
docker-compose -f docker-compose.production.yml logs web
```

### Database connection issues
```bash
docker-compose -f docker-compose.production.yml exec web python manage.py dbshell
```

### Static files not loading
```bash
docker-compose -f docker-compose.production.yml exec web python manage.py collectstatic --clear --noinput
```

### Reset everything (WARNING: Deletes all data!)
```bash
docker-compose -f docker-compose.production.yml down -v
docker-compose -f docker-compose.production.yml up -d
```
