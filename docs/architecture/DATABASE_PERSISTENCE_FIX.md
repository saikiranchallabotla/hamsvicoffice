# Database Persistence Issue - Railway Deployment

## Problem
User data is being lost on every redeployment because the app is using **SQLite** (file-based database) which is **ephemeral** on Railway.

### Current Setup
- **Database Type**: SQLite (`db.sqlite3`)
- **Storage Location**: `/app/db.sqlite3` (ephemeral volume)
- **On Redeployment**: File is deleted, all user data lost
- **Users Affected**: All previously registered users

### Why This Happens
Railway containers are **stateless** - file changes don't persist between deployments. SQLite relies on files, so:
1. Deploy 1: Users register → data in `db.sqlite3`
2. Redeployment: Container dies → `db.sqlite3` deleted
3. Deploy 2: New container starts with fresh empty database
4. Previous users are gone

## Solution Options

### Option 1: Use PostgreSQL (RECOMMENDED ⭐)
Railway provides free PostgreSQL databases. This is the **best solution** for production.

**Steps:**
1. Add PostgreSQL service to your Railway project (Railway dashboard)
2. Railway automatically sets `DATABASE_URL` environment variable
3. Django reads `DATABASE_URL` and uses PostgreSQL automatically
4. **Data persists across redeployments**

**Cost**: Free tier includes 256MB PostgreSQL

---

### Option 2: Use Railway PostgreSQL Plugin (EASIER)
1. Go to Railway dashboard → Your Project
2. Add new "Database" service
3. Select PostgreSQL
4. Railway auto-links it via `DATABASE_URL`
5. No code changes needed - Django will use it automatically

**Verification:**
```bash
# Check if DATABASE_URL is set on Railway
echo $DATABASE_URL
```

---

### Option 3: Migrate SQLite Data to PostgreSQL (Keep Existing Users)
If you want to preserve existing users from SQLite:

**Local Steps:**
```bash
# Export SQLite data
python manage.py dumpdata > data.json

# Configure PostgreSQL locally
# Update settings with PostgreSQL credentials
python manage.py migrate

# Import data
python manage.py loaddata data.json
```

---

## Quick Verification Checklist

### Is DATABASE_URL configured?
```python
# In settings.py or settings_railway.py, check:
DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL:
    print("✅ Using PostgreSQL from DATABASE_URL")
else:
    print("❌ DATABASE_URL not set - using SQLite (ephemeral!)")
```

### Current Database Type
Check which database is being used:
```bash
# SSH into Railway container and check:
echo $DATABASE_URL  # Should be postgres://...

# If empty, you're using SQLite (❌ loses data on redeploy)
# If set, you're using PostgreSQL (✅ data persists)
```

---

## Implementation (5 minutes)

### Step 1: Add PostgreSQL to Railway
1. Go to `railway.app`
2. Open your Hamsvic project
3. Click "+ Add"
4. Select "PostgreSQL"
5. Wait for it to provision (1-2 minutes)

### Step 2: Verify Connection
Railway automatically adds `DATABASE_URL` environment variable.

Check Django logs after redeploy:
```
✅ "using PostgreSQL" (good)
❌ "using SQLite" (bad - DATABASE_URL not set)
```

### Step 3: Migrate Database (First Time Only)
```bash
# Railway automatically runs this in startCommand:
python manage.py migrate

# Create superuser for admin panel
python manage.py createsuperuser
```

### Step 4: Test
1. Register a new user
2. Redeploy the app
3. Login - user should still exist ✅

---

## Code References

### Current Settings (NEED FIX)
**File**: `estimate_site/settings_railway.py` (Lines 91-102)

```python
DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(default=DATABASE_URL, conn_max_age=600)
    }
else:
    # ❌ PROBLEM: Falls back to SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
```

**Fix**: Remove SQLite fallback - require PostgreSQL on Railway:

```python
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ImproperlyConfigured('DATABASE_URL must be set for Railway deployments')

DATABASES = {
    'default': dj_database_url.config(default=DATABASE_URL, conn_max_age=600)
}
```

---

## Troubleshooting

### "Users disappeared after redeployment"
- **Cause**: Using SQLite on Railway
- **Fix**: Add PostgreSQL service from Railway dashboard

### "DATABASE_URL is set but still getting error"
- **Check**: Is PostgreSQL service running in Railway? (check Deployments tab)
- **Fix**: Restart the service or redeploy the app

### "Want to keep existing users"
- Existing data is already lost (SQLite was deleted)
- Add PostgreSQL now for future persistence
- New registrations will be saved

### "Want to migrate data from SQLite to PostgreSQL"
If you have a local SQLite backup:
```bash
# Export
python manage.py dumpdata > backup.json

# Migrate to PostgreSQL (locally or on Railway)
python manage.py migrate
python manage.py loaddata backup.json
```

---

## Summary

| Feature | SQLite (Current) | PostgreSQL (Recommended) |
|---------|------------------|-------------------------|
| Data Persists | ❌ Deleted on redeployment | ✅ Always persisted |
| Cost | Free | Free (Railway tier) |
| Setup Time | None | 2 minutes |
| Production Ready | ❌ No | ✅ Yes |
| User Data Loss | ⚠️ Yes on each deploy | ✅ No |

**Action Required**: Add PostgreSQL to Railway project (free service)

---

## Next Steps

1. ✅ Open Railway dashboard
2. ✅ Click "+ Add" in your Hamsvic project
3. ✅ Select "PostgreSQL"
4. ✅ Wait for provisioning
5. ✅ Redeploy your app
6. ✅ Test by registering a new user
7. ✅ Redeploy again - user should still exist

**Expected Result**: All user data persists across redeployments ✨
