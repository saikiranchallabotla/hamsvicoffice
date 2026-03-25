# Hamsvic Office - Setup Guide

## Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- PostgreSQL 14+ (or SQLite for quick testing)
- Redis (for caching and background tasks)

### 1. Clone and Configure

```bash
git clone <repository-url>
cd hamsvicoffice
cp .env.example .env
```

Edit `.env` and set your values (especially `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and `DJANGO_SECRET_KEY`).

### 2. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate   # Linux/Mac
# venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

### 3. Start the Application

```bash
python init_app.py    # Runs migrations, creates admin, seeds data
python manage.py runserver
```

Visit `http://localhost:8000` and log in with the admin credentials you set in `.env`.

### 4. (Optional) Start Background Workers

```bash
celery -A estimate_site worker -l info
celery -A estimate_site beat -l info
```

---

## Docker Setup (Recommended)

```bash
cp .env.example .env
# Edit .env with your values
docker-compose up --build
```

This starts Django, PostgreSQL, and Redis together.

---

## Production Deployment (Railway)

### 1. Create a Railway Project
- Go to [railway.app](https://railway.app) and create a new project
- Add PostgreSQL and Redis services

### 2. Set Environment Variables
Copy all variables from `.env.production.example` and set actual values in Railway's dashboard.

**Required variables:**
- `DJANGO_SECRET_KEY` - Generate with: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
- `ADMIN_EMAIL` / `ADMIN_PASSWORD` - Your admin login credentials
- `ALLOWED_HOSTS` - Your domain name
- Database variables (auto-set by Railway if using their PostgreSQL)

### 3. Deploy
Railway auto-deploys on `git push`. The `Procfile` handles startup.

### 4. (Optional) Set Up File Storage
For persistent file storage, configure S3 or Cloudflare R2:
- Set `STORAGE_TYPE=s3` or `STORAGE_TYPE=r2`
- Set AWS credentials (see `.env.production.example`)

### 5. (Optional) Set Up Payments
- Create a [Razorpay](https://razorpay.com) account
- Set `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`

### 6. (Optional) Set Up OTP Verification
- Create a [Twilio](https://twilio.com) account
- Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`

---

## SOR Data (Schedule of Rates)

The app comes with default SOR data files in `core/data/`. To load them into the database:

```bash
# Set this env var on first deploy only
SEED_INITIAL_BACKENDS=true
```

After the first deploy, remove this variable. Admin users can upload updated SOR data through the admin panel.

---

## Module Overview

| Module | Description |
|--------|-------------|
| New Estimate | Create estimates from SOR data |
| Estimate | Manage and track estimates |
| Workslip | Generate work slips from estimates |
| Bill | Create bills (1st through Final) |
| Self Formatted | OCR-based custom documents |
| Temporary Works | Manage temporary project items |
| AMC | Annual Maintenance Contracts |

---

## Support

For questions or issues, contact: support@hamsvic.com
