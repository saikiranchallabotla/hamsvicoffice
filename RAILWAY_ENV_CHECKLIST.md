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

### 7️⃣ S3 Storage (files persist across deployments)
```
STORAGE_TYPE=s3
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_STORAGE_BUCKET_NAME=your-bucket
AWS_S3_REGION_NAME=ap-south-1
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
   - ✅ Fix: Configure S3 storage for production
   
2. **Background Tasks**: Running synchronously (slower for heavy Excel processing)
   - ✅ Fix: Configure Redis + Celery worker for production

3. **Session Cache**: Using in-memory cache (not shared across instances)
   - ✅ Fix: Configure Redis for multi-instance deployments

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
