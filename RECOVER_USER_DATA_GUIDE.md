# Recover Lost User Data from PostgreSQL

## Situation
- You've been using PostgreSQL
- User data appears to be lost
- But if PostgreSQL was configured, the data should still be in the database

## Step 1: Verify PostgreSQL is Actually Connected

### Check Railway Logs
1. Go to `railway.app` → Your Project
2. Click on the app (not the database)
3. Go to "Deployments" tab
4. Click latest deployment
5. Look for logs like:
   - ✅ "PostgreSQL connected" or "using postgres://" - Good!
   - ❌ "SQLite" or no database mention - Problem!

### Check Environment Variables on Railway
1. Go to `railway.app` → Your Project
2. Click the app service
3. Go to "Variables" tab
4. Look for `DATABASE_URL` variable
   - ✅ If it shows `postgres://...` - PostgreSQL is configured
   - ❌ If it's missing or blank - SQLite is being used (data lost)

### SSH into Railway Container (Advanced)
```bash
# Connect to Railway container
railway shell

# Check if DATABASE_URL is set
echo $DATABASE_URL

# If output is postgres://... then data is in PostgreSQL database
# If empty, you're using SQLite (ephemeral)
```

---

## Step 2: If PostgreSQL is Configured - Recover Data

If `DATABASE_URL` is set to PostgreSQL, your user data is **still in the database** and can be recovered!

### Option A: Query Users from Railway PostgreSQL

**Using Django Shell** (SSH into Railway):
```bash
railway shell
python manage.py shell

# Inside Django shell:
from django.contrib.auth.models import User
all_users = User.objects.all()
for user in all_users:
    print(f"Username: {user.username}, Email: {user.email}, First Name: {user.first_name}")
```

**Expected Output:**
```
Username: saikiran, Email: saikiran@example.com, First Name: Saikiran
Username: john_doe, Email: john@example.com, First Name: John
...
```

If you see users, **your data is safe and recovered!** ✅

### Option B: Export All User Data

```bash
railway shell

# Export all users to JSON file
python manage.py dumpdata auth.user accounts.userprofile > users_backup.json

# Download the file (check Railway file system)
# Or use this to verify in shell:
cat users_backup.json
```

### Option C: Admin Panel Check

1. Go to your app URL: `https://your-app.railway.app/admin/`
2. Login with superuser credentials
3. Go to "Users" section
4. All registered users should be visible here

If users are showing up, data is NOT lost! ✅

---

## Step 3: If PostgreSQL is NOT Configured

If `DATABASE_URL` is empty/missing:

### Problem
- You're using SQLite, not PostgreSQL
- SQLite file is deleted on each redeployment
- Data is truly lost

### Solution
1. Go to Railway dashboard
2. Click your Hamsvic project
3. Click "+ Add" → "PostgreSQL"
4. Wait for provisioning (auto-creates DATABASE_URL)
5. Redeploy your app
6. Verify DATABASE_URL is now set
7. Users registered after this will persist ✅

---

## Step 4: Why Data Seems Lost

### Scenario 1: PostgreSQL configured but appears empty
- ✅ New user registered → saved to PostgreSQL
- ✅ Redeployed → PostgreSQL still has the data
- ❌ But migrations might have reset tables
  - **Solution**: Check if migrations ran correctly
  
```bash
railway shell
python manage.py showmigrations
python manage.py migrate --check  # Shows pending migrations
```

### Scenario 2: SQLite was being used
- ✅ User registered → saved to `db.sqlite3` file
- ❌ Redeployed → `db.sqlite3` file deleted
- ❌ Data truly gone (SQLite is ephemeral)
  - **Solution**: Add PostgreSQL now

### Scenario 3: PostgreSQL configured but wrong environment
- ✅ Users registered on prod (PostgreSQL)
- ❌ Checking local dev (SQLite)
- **Solution**: Make sure you're checking Railway admin panel, not local

---

## Verification Checklist

- [ ] Check Railway Variables tab - is `DATABASE_URL` set?
- [ ] Check logs - does it say "PostgreSQL" or "SQLite"?
- [ ] SSH into container - echo $DATABASE_URL shows postgres://...?
- [ ] Run Django shell - User.objects.all() returns your users?
- [ ] Check admin panel - /admin/ shows users in database?
- [ ] Check migrations - showmigrations shows all applied?

---

## Quick Commands to Test

### SSH into Railway
```bash
railway shell
```

### Check database type
```bash
echo $DATABASE_URL
# If postgres:// then PostgreSQL is configured ✅
# If empty then SQLite is being used ❌
```

### See all users
```bash
python manage.py shell
from django.contrib.auth.models import User
print(f"Total users: {User.objects.count()}")
for u in User.objects.all():
    print(f"  - {u.username}")
```

### Check if migrations are applied
```bash
python manage.py showmigrations
# All should show ✓ (checkmark)
```

### Export user data
```bash
python manage.py dumpdata auth.user accounts > users_export.json
cat users_export.json
```

---

## Expected Results

### ✅ Data is Recoverable (Best Case)
- DATABASE_URL is set to PostgreSQL
- Django shell shows users
- Admin panel displays users
- Migrations are all applied

**Action**: Data is safe, just query it from admin panel or shell

---

### ❌ Data is Lost (Worst Case)
- DATABASE_URL is empty/missing
- Only SQLite was used
- Migrations table was deleted
- No users in database

**Action**: 
1. Add PostgreSQL now
2. Accept data loss (previous data is gone)
3. New users registered after PostgreSQL setup will persist

---

## How to Verify Right Now

Run these 3 commands on Railway:

```bash
# 1. Check if PostgreSQL is configured
railway shell
echo "DATABASE_URL: $DATABASE_URL"

# 2. Count total users in database
python manage.py shell
from django.contrib.auth.models import User
print(f"Users in database: {User.objects.count()}")
exit()

# 3. Check if migrations are applied
python manage.py showmigrations auth
exit()
```

**Share the output** and I can tell you exactly what happened and how to recover data!
