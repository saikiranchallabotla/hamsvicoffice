# Data Persistence Setup Guide

## 🚨 Problem: User Data Lost on Redeployment

If you're seeing user data disappear after each deployment, it's because of one or both of these issues:

1. **SQLite Database** - Database file deleted on each deploy
2. **Local File Storage** - Uploaded template files deleted on each deploy

This affects:
- ✉️ **Forwarding Letter Details** (LetterSettings model)
- 💾 **Saved Works** (SavedWork model) 
- 📄 **Self-Formatted Templates** (SelfFormattedTemplate model)
- 👤 **User Accounts** (User model)

---

## ✅ Solution 1: Add PostgreSQL Database (REQUIRED)

PostgreSQL data persists across deployments. This is **FREE** on Railway.

### Railway Setup (2 minutes):

1. **Open Railway Dashboard**
   - Go to https://railway.app
   - Open your Hamsvic project

2. **Add PostgreSQL**
   - Click **"+ Add"** button (top right)
   - Select **"PostgreSQL"**
   - Wait 1-2 minutes for provisioning

3. **Verify Connection**
   - Railway automatically sets `DATABASE_URL` environment variable
   - Redeploy your app
   - Check logs for: `✅ DATABASE: PostgreSQL (persistent)`

### Manual PostgreSQL Setup (AWS RDS, Neon, etc.):

Set these environment variables:
```env
DB_ENGINE=postgresql
DB_HOST=your-host.db.example.com
DB_NAME=hamsvic
DB_USER=hamsvic_user
DB_PASSWORD=your-secure-password
DB_PORT=5432
```

Or set the full connection URL:
```env
DATABASE_URL=postgres://user:password@host:5432/database
```

---

## ✅ Solution 2: Add Cloud File Storage (RECOMMENDED)

For uploaded files (Self-Formatted Templates) to persist, use cloud storage.

### Option A: Cloudflare R2 (Cheapest - 10GB free)

1. Create R2 bucket at https://dash.cloudflare.com
2. Create API token with R2 read/write access
3. Set environment variables:

```env
STORAGE_TYPE=r2
AWS_ACCESS_KEY_ID=your-r2-access-key-id
AWS_SECRET_ACCESS_KEY=your-r2-secret-access-key
AWS_STORAGE_BUCKET_NAME=hamsvic-uploads
AWS_S3_ENDPOINT_URL=https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com
AWS_S3_REGION_NAME=auto
```

### Option B: AWS S3

1. Create S3 bucket in AWS Console
2. Create IAM user with S3 access
3. Set environment variables:

```env
STORAGE_TYPE=s3
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_STORAGE_BUCKET_NAME=hamsvic-uploads
AWS_S3_REGION_NAME=ap-south-1
```

### Option C: DigitalOcean Spaces

```env
STORAGE_TYPE=s3
AWS_ACCESS_KEY_ID=your-do-spaces-key
AWS_SECRET_ACCESS_KEY=your-do-spaces-secret
AWS_STORAGE_BUCKET_NAME=hamsvic-uploads
AWS_S3_ENDPOINT_URL=https://sgp1.digitaloceanspaces.com
AWS_S3_REGION_NAME=sgp1
```

---

## 🔍 Verification Checklist

After configuring, check your app logs for:

```
[INIT] ================================================
[INIT] DATA PERSISTENCE STATUS CHECK
[INIT] ================================================
[INIT] ✅ DATABASE: PostgreSQL (persistent)
[INIT]    • Users: 5
[INIT]    • Letter Settings: 3
[INIT]    • Saved Works: 12
[INIT]    • Self-Formatted Templates: 2
[INIT] ✅ FILE STORAGE: S3/R2 (bucket: hamsvic-uploads) (persistent)
[INIT] ------------------------------------------------
[INIT] ✅ All data persistence checks PASSED
[INIT] ✅ User data WILL persist across deployments
[INIT] ================================================
```

---

## 📋 Environment Variables Summary

### Required for Data Persistence:
```env
# Option 1: Railway PostgreSQL (auto-set)
DATABASE_URL=postgres://...

# Option 2: Manual PostgreSQL
DB_ENGINE=postgresql
DB_HOST=your-host
DB_NAME=hamsvic
DB_USER=postgres
DB_PASSWORD=your-password
```

### Recommended for File Persistence:
```env
STORAGE_TYPE=s3  # or r2
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_STORAGE_BUCKET_NAME=your-bucket
AWS_S3_ENDPOINT_URL=https://...  # Only for R2/Spaces
```

---

## 🛠️ What Each Data Type Needs

| Data Type | PostgreSQL | Cloud Storage | Admin Edits Preserved? |
|-----------|------------|---------------|------------------------|
| User Accounts | ✅ Required | - | ✅ Yes |
| Forwarding Letter Details | ✅ Required | - | ✅ Yes |
| Saved Works | ✅ Required | - | ✅ Yes |
| Self-Formatted Templates (metadata) | ✅ Required | - | ✅ Yes |
| Self-Formatted Templates (files) | - | ✅ Required | ✅ Yes |
| Module Backends / SOR Data | ✅ Required | ✅ Recommended | ✅ Yes |
| Backend Excel Files | - | ✅ Recommended | ✅ Yes |
| Generated Output Files | - | ✅ Recommended | N/A |

### Module Backends (SOR Rate Books) Behavior

The system intelligently handles backend data on deployment:

1. **First deployment**: Creates initial backends from bundled static files
2. **Subsequent deployments**: 
   - **Never overwrites** existing backend records
   - Preserves all admin customizations (name, settings, active status)
   - Only restores missing files (for local storage without cloud backup)
3. **Admin edits**: Once an admin edits a backend, it's never touched again

This means:
- ✅ Admin-uploaded SOR rate books are preserved
- ✅ Backend name changes are preserved  
- ✅ Active/inactive status is preserved
- ✅ Custom backends added by admin are preserved

---

## 📞 Quick Commands

### Check current database configuration:
```python
# In Django shell
from django.conf import settings
print(settings.DATABASES['default']['ENGINE'])
# Should output: django.db.backends.postgresql
```

### Check current storage configuration:
```python
from django.conf import settings
print(settings.STORAGES['default']['BACKEND'])
# Should output: storages.backends.s3boto3.S3Boto3Storage
```

### Count persisted user data:
```python
from django.contrib.auth.models import User
from core.models import LetterSettings, SavedWork, SelfFormattedTemplate

print(f"Users: {User.objects.count()}")
print(f"Letter Settings: {LetterSettings.objects.count()}")
print(f"Saved Works: {SavedWork.objects.count()}")
print(f"Templates: {SelfFormattedTemplate.objects.count()}")
```

---

## ⚠️ If Data Was Already Lost

Unfortunately, if you were using SQLite without backups, the data cannot be recovered.

**Going forward:**
1. Set up PostgreSQL (following this guide)
2. Users will need to re-enter their Forwarding Letter Details
3. Saved Works will need to be recreated
4. Self-Formatted Templates will need to be re-uploaded

---

## 📌 Railway Deployment Checklist

Before every production deployment:

- [ ] `DATABASE_URL` is set (check Railway Variables tab)
- [ ] PostgreSQL service is running in Railway project
- [ ] (Optional) Cloud storage configured for file uploads
- [ ] App logs show `✅ DATABASE: PostgreSQL (persistent)`
- [ ] App logs show `✅ All data persistence checks PASSED`

---

*Last Updated: February 2026*
