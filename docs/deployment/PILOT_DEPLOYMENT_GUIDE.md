# 🚀 HAMSVIC Pilot Deployment - Simple Guide

## For 5-10 Test Users (Zero Technical Knowledge Required)

---

## 📌 Choose Your Deployment Option

| Option | Cost | Difficulty | Time | Best For |
|--------|------|------------|------|----------|
| **Railway.app** | FREE-₹500/mo | ⭐ Very Easy | 15 min | Beginners |
| **Render.com** | FREE-₹600/mo | ⭐ Very Easy | 20 min | Beginners |
| **PythonAnywhere** | ₹400/mo | ⭐⭐ Easy | 30 min | Simple setup |
| **DigitalOcean** | ₹800/mo | ⭐⭐⭐ Medium | 1 hour | More control |

---

## 🎯 RECOMMENDED: Railway.app Deployment

### Prerequisites
1. A GitHub account (free) - https://github.com
2. A Railway account (free) - https://railway.app

---

## Step 1: Create GitHub Account & Repository

### 1.1 Create GitHub Account
1. Go to https://github.com
2. Click "Sign Up"
3. Enter your email, create password, choose username
4. Verify your email

### 1.2 Install Git on Your Computer
1. Download from: https://git-scm.com/download/win
2. Run the installer (accept all defaults)
3. Restart your computer

### 1.3 Upload Your Project to GitHub
Open **PowerShell** in your project folder and run these commands ONE BY ONE:

```powershell
# Navigate to your project (change path if needed)
cd "E:\Version 3\Windows x 1"

# Initialize Git
git init

# Add all files
git add .

# Create first commit
git commit -m "Initial commit for deployment"

# Create repository on GitHub first, then:
# Replace YOUR_USERNAME with your GitHub username
# Replace hamsvic with your desired repository name
git remote add origin https://github.com/YOUR_USERNAME/hamsvic.git

# Push to GitHub
git branch -M main
git push -u origin main
```

**Note:** GitHub will ask for your credentials. Use your GitHub username and a Personal Access Token (not password).

#### Creating Personal Access Token:
1. Go to GitHub → Settings → Developer Settings → Personal Access Tokens → Tokens (classic)
2. Generate new token
3. Select scopes: `repo` (full control)
4. Copy and save the token - use this as your password

---

## Step 2: Deploy on Railway.app

### 2.1 Create Railway Account
1. Go to https://railway.app
2. Click "Login with GitHub"
3. Authorize Railway

### 2.2 Create New Project
1. Click **"New Project"**
2. Select **"Deploy from GitHub repo"**
3. Choose your `hamsvic` repository
4. Railway will auto-detect Django and start building

### 2.3 Add PostgreSQL Database
1. In your project, click **"+ New"**
2. Select **"Database"** → **"PostgreSQL"**
3. Railway automatically connects it to your app

### 2.4 Add Environment Variables
1. Click on your web service
2. Go to **"Variables"** tab
3. Add these variables:

```
DEBUG=False
SECRET_KEY=your-super-secret-random-string-make-it-very-long-32-chars-minimum
ALLOWED_HOSTS=.railway.app
```

**Generate a SECRET_KEY:** Use this Python command:
```python
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### 2.5 Get Your Live URL
1. Go to **"Settings"** tab
2. Under **"Domains"**, click **"Generate Domain"**
3. Your app is now live at: `https://your-project.railway.app`

---

## Step 3: First-Time Setup (After Deployment)

### 3.1 Create Admin User
In Railway:
1. Go to your web service
2. Click **"Shell"** tab (or use the command palette)
3. Run:
```bash
python manage.py createsuperuser
```
4. Enter username, email, and password

### 3.2 Access Admin Panel
Go to: `https://your-project.railway.app/admin`

---

## 🎉 Congratulations! Your App is Live!

Share the URL with your 5-10 test users:
- **Main Site:** `https://your-project.railway.app`
- **Admin Panel:** `https://your-project.railway.app/admin`

---

## 💡 Alternative: Render.com (Also Very Easy)

### Step 1: Create Render Account
1. Go to https://render.com
2. Sign up with GitHub

### Step 2: Create Web Service
1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub repository
3. Configure:
   - **Name:** hamsvic
   - **Region:** Singapore (closest to India)
   - **Branch:** main
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn estimate_site.wsgi`

### Step 3: Add Environment Variables
Same as Railway - add DEBUG, SECRET_KEY, ALLOWED_HOSTS

### Step 4: Add PostgreSQL
1. Click **"New +"** → **"PostgreSQL"**
2. Connect to your web service

---

## 🔧 Troubleshooting

### "Application Error" or "502 Bad Gateway"
1. Check logs in Railway/Render dashboard
2. Make sure all environment variables are set
3. Ensure `requirements.txt` has all dependencies

### "Static files not loading"
1. Run `python manage.py collectstatic`
2. Or add to environment: `DISABLE_COLLECTSTATIC=0`

### "Database error"
1. Run migrations: `python manage.py migrate`
2. Check DATABASE_URL is set correctly

### "Module not found"
1. Check `requirements.txt` includes all packages
2. Rebuild the deployment

---

## 📞 Need Help?

If you get stuck:
1. Check the deployment logs (shows exact error)
2. Search the error message on Google
3. Railway/Render have great documentation and Discord communities

---

## 📊 Monitoring Your Pilot

### User Feedback Collection
1. Create a simple Google Form for feedback
2. Share it with your test users
3. Collect issues and suggestions

### What to Monitor
- [ ] Can users register/login?
- [ ] Can users upload files?
- [ ] Are estimates generating correctly?
- [ ] Any error messages?
- [ ] Is the app fast enough?

---

## 🔄 Making Updates

When you need to update your app:

```powershell
# Make your changes locally
# Then commit and push:
git add .
git commit -m "Description of changes"
git push
```

Railway/Render will automatically redeploy!

---

## 💰 Cost Summary for Pilot (5-10 Users)

| Service | Free Tier | Paid Tier |
|---------|-----------|-----------|
| Railway | 500 hours/month free | $5/month |
| Render | 750 hours/month free | $7/month |
| Database | Free tier available | $5-15/month |

**Total for Pilot:** ₹0-1000/month

---

## 🚀 When Ready to Scale

Once your pilot is successful and you want to grow:
1. Get a custom domain (₹500-1000/year)
2. Upgrade to paid tier for better performance
3. Consider AWS/DigitalOcean for more control
4. Set up proper monitoring (Sentry for errors)

Good luck with your pilot! 🎉
