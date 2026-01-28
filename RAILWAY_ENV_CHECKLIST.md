# 🚂 Railway Environment Variables Checklist

## CRITICAL - Required for App to Work

Set these in Railway → Your Service → Variables:

### 1️⃣ Django Core (REQUIRED)
```
SECRET_KEY=<generate-with: python -c "import secrets; print(secrets.token_urlsafe(50))">
DEBUG=False
ALLOWED_HOSTS=.railway.app,.up.railway.app
```

### 2️⃣ Database (AUTO-SET by Railway)
```
DATABASE_URL=<auto-populated when you add PostgreSQL service>
```

### 3️⃣ Settings Module (REQUIRED)
```
DJANGO_SETTINGS_MODULE=estimate_site.settings_railway
```

---

## RECOMMENDED - For Full Feature Parity

### 4️⃣ Email Configuration (for OTP)
For pilot testing, emails print to logs. For production:
```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@hamsvic.com
```

### 5️⃣ SMS Configuration (for OTP via SMS)
Leave empty for DEV MODE (OTP shown on screen):
```
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
```

### 6️⃣ Payment Gateway (for subscriptions)
```
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx
RAZORPAY_KEY_SECRET=your-secret
RAZORPAY_WEBHOOK_SECRET=your-webhook-secret
```

---

## OPTIONAL - For Production Scale

### 7️⃣ Cloud Storage (⚠️ IMPORTANT - files persist across deployments)

**Without cloud storage, user uploaded files and generated outputs are LOST on every redeploy!**

#### Option A: Cloudflare R2 (RECOMMENDED - 10GB FREE)
```
STORAGE_TYPE=r2
AWS_ACCESS_KEY_ID=your-r2-access-key
AWS_SECRET_ACCESS_KEY=your-r2-secret-key
AWS_STORAGE_BUCKET_NAME=hamsvic
AWS_S3_ENDPOINT_URL=https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com
AWS_S3_REGION_NAME=auto
```

**R2 Setup Steps:**
1. Go to https://dash.cloudflare.com → R2 Object Storage
2. Create bucket named "hamsvic" (or your preferred name)
3. Go to R2 → Manage R2 API Tokens → Create API Token
4. Select "Object Read & Write" permission, select your bucket
5. Copy Access Key ID and Secret Access Key
6. Account ID is in the URL or R2 dashboard
7. Add all variables to Railway

#### Option B: AWS S3
```
STORAGE_TYPE=s3
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_STORAGE_BUCKET_NAME=your-bucket
AWS_S3_REGION_NAME=ap-south-1
```

#### Option C: DigitalOcean Spaces
```
STORAGE_TYPE=s3
AWS_ACCESS_KEY_ID=your-spaces-key
AWS_SECRET_ACCESS_KEY=your-spaces-secret
AWS_STORAGE_BUCKET_NAME=your-space-name
AWS_S3_ENDPOINT_URL=https://blr1.digitaloceanspaces.com
AWS_S3_REGION_NAME=blr1
```

### 8️⃣ Redis Cache (for better performance)
```
REDIS_URL=redis://your-redis-url
CELERY_BROKER_URL=redis://your-redis-url
CELERY_RESULT_BACKEND=redis://your-redis-url
CELERY_TASK_ALWAYS_EAGER=False
```

### 9️⃣ Error Monitoring
```
SENTRY_DSN=your-sentry-dsn
```

---

## ⚠️ KNOWN PILOT LIMITATIONS

1. **File Storage**: Using local filesystem - files are LOST on redeploy
   - ✅ Fix: Configure Cloudflare R2 (free 10GB) or S3 storage (see section 7️⃣)
   - Module backends are auto-restored from static files on startup
   - User uploaded files need cloud storage to persist
   
2. **Background Tasks**: Running synchronously (slower for heavy Excel processing)
   - ✅ Fix: Configure Redis + Celery worker for production

3. **Session/Cache**: Using database-backed cache (persists across redeploys)
   - ✅ Already configured for persistence
   - For better performance: Configure Redis

---

## 🔍 Quick Verification Commands

After deployment, access Railway shell and run:

```bash
# Check migrations
python manage.py showmigrations

# Verify admin user
python manage.py shell -c "from django.contrib.auth import get_user_model; print(get_user_model().objects.filter(is_superuser=True).values_list('email', flat=True))"

# Check modules are seeded
python manage.py shell -c "from subscriptions.models import Module; print(list(Module.objects.values_list('code', flat=True)))"

# Verify backend data files exist
python manage.py shell -c "import os; from django.conf import settings; print([f for f in os.listdir(settings.BASE_DIR / 'core' / 'data') if f.endswith('.xlsx')])"
```

---

## 🚀 Post-Deployment Checklist

- [ ] Can access `/health/` endpoint
- [ ] Can access `/admin/` panel
- [ ] Can login with admin credentials
- [ ] Dashboard loads correctly
- [ ] Can navigate to New Estimate module
- [ ] Backend data (electrical/civil groups) loads
- [ ] Can upload an estimate Excel file
- [ ] Workslip generation works
- [ ] Bill generation works

---

## 📞 Support

If deployment fails, check Railway logs for:
- `ModuleNotFoundError` → Missing in requirements.txt
- `OperationalError` → Database not connected
- `FileNotFoundError` → Backend Excel files not in git
