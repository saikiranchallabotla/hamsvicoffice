"""
Railway-specific settings - minimal configuration for pilot deployment
"""
from pathlib import Path
import os
import sys
import dj_database_url

# Increase recursion limit
sys.setrecursionlimit(5000)

BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================================================================
# CORE SETTINGS
# ==============================================================================
# SECRET_KEY MUST be set in Railway environment variables for session persistence
# If not set, sessions will be invalidated on every deployment!
# Checks both SECRET_KEY and DJANGO_SECRET_KEY for compatibility
SECRET_KEY = os.environ.get('SECRET_KEY') or os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-fallback-set-secret-key-in-railway')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = ['*']  # Railway handles this at proxy level

# CSRF Trusted Origins for Railway
CSRF_TRUSTED_ORIGINS = [
    'https://*.railway.app',
    'https://*.up.railway.app',
]

# Add custom domain if configured
CUSTOM_DOMAIN = os.environ.get('CUSTOM_DOMAIN', '')
if CUSTOM_DOMAIN:
    CSRF_TRUSTED_ORIGINS.append(f'https://{CUSTOM_DOMAIN}')
    CSRF_TRUSTED_ORIGINS.append(f'http://{CUSTOM_DOMAIN}')

# ==============================================================================
# APPLICATION CONFIGURATION
# ==============================================================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'storages',  # django-storages for S3/DO Spaces
    'django_celery_beat',  # Celery beat scheduler

    # Local apps
    'core',
    'accounts',
    'subscriptions',
    'datasets',
    'support',
    'admin_panel',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.OrganizationMiddleware',
    
    # Session & Subscription Middleware
    'accounts.middleware.SessionTrackingMiddleware',
    'accounts.middleware.ConcurrentSessionCheckMiddleware',
    'subscriptions.middleware.SubscriptionCacheMiddleware',
    'subscriptions.middleware.ModuleAccessMiddleware',
    'subscriptions.middleware.UsageTrackingMiddleware',
]

# Maximum concurrent sessions per user
MAX_CONCURRENT_SESSIONS = 1

ROOT_URLCONF = 'estimate_site.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'estimate_site.wsgi.application'

# ==============================================================================
# DATABASE - Railway PostgreSQL (Required)
# ==============================================================================
# Supports three configuration methods:
# 1. DATABASE_URL (preferred - auto-set by Railway)
# 2. Individual DB_* environment variables (DB_ENGINE, DB_HOST, DB_NAME, etc.)
# 3. SQLite fallback (development only - ephemeral on Railway!)

import logging
logger = logging.getLogger('estimate_site.settings')

DATABASE_URL = os.environ.get('DATABASE_URL', '')
DB_ENGINE = os.environ.get('DB_ENGINE', 'sqlite3')

if DATABASE_URL:
    # ✅ Using DATABASE_URL (Railway auto-provided PostgreSQL)
    logger.info('✅ Database: PostgreSQL via DATABASE_URL')
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
elif DB_ENGINE in ('postgresql', 'postgres', 'postgres_psycopg2'):
    # ✅ Using individual PostgreSQL variables (DB_HOST, DB_NAME, etc.)
    logger.info('✅ Database: PostgreSQL via individual DB_* variables')
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'hamsvic'),
            'USER': os.environ.get('DB_USER', 'postgres'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
            'ATOMIC_REQUESTS': True,
            'CONN_MAX_AGE': 600,
            'OPTIONS': {
                'sslmode': 'require',
            },
        }
    }
else:
    # ⚠️ WARNING: No PostgreSQL configured - using SQLite
    # This is DANGEROUS in production environments!
    logger.critical(
        '❌ WARNING: Using SQLite (ephemeral storage on Railway)! '
        'User data WILL BE LOST on each redeployment. '
        'To fix: Set DATABASE_URL or DB_ENGINE=postgresql with DB_* variables'
    )
    
    # In Railway production environment, refuse to start without PostgreSQL
    # This prevents silent data loss
    if os.environ.get('RAILWAY_ENVIRONMENT') and os.environ.get('REQUIRE_POSTGRES', 'false').lower() == 'true':
        raise RuntimeError(
            "CRITICAL: No PostgreSQL database configured!\n"
            "User data (LetterSettings, SavedWorks, Templates) will be lost on every deploy.\n"
            "To fix:\n"
            "1. Add PostgreSQL to your Railway project (free)\n"
            "2. Railway will auto-set DATABASE_URL\n"
            "3. Redeploy\n"
            "Or set REQUIRE_POSTGRES=false to use SQLite (NOT recommended for production)"
        )
    
    # Fall back to SQLite for development (ephemeral on Railway!)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ==============================================================================
# STATIC FILES - WhiteNoise
# ==============================================================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ==============================================================================
# FILE STORAGE CONFIGURATION
# ==============================================================================
# Priority: 
# 1. S3/R2 (set STORAGE_TYPE=s3 and provide credentials) - RECOMMENDED FOR PRODUCTION
# 2. Railway Volume (mount at /app/media) - Good alternative
# 3. Local filesystem (ephemeral - files lost on redeploy!) - ONLY FOR DEV

STORAGE_TYPE = os.environ.get('STORAGE_TYPE', 'local')

# S3-compatible storage credentials (works with AWS S3, Cloudflare R2, DigitalOcean Spaces)
_aws_key = os.environ.get('AWS_ACCESS_KEY_ID', '')
_aws_secret = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
_bucket_name = os.environ.get('AWS_STORAGE_BUCKET_NAME', 'hamsvic')
_endpoint_url = os.environ.get('AWS_S3_ENDPOINT_URL', None)  # Required for R2/Spaces
_region = os.environ.get('AWS_S3_REGION_NAME', 'auto')  # 'auto' for R2

# Determine if we can use S3 storage
_use_s3 = (STORAGE_TYPE == 's3' or STORAGE_TYPE == 'r2') and _aws_key and _aws_secret

if _use_s3:
    # S3-compatible storage (AWS S3, Cloudflare R2, DigitalOcean Spaces)
    # Cloudflare R2: Set AWS_S3_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "access_key": _aws_key,
                "secret_key": _aws_secret,
                "bucket_name": _bucket_name,
                "region_name": _region,
                "endpoint_url": _endpoint_url,
                "default_acl": None,  # R2 doesn't support ACLs
                "file_overwrite": False,
                "object_parameters": {
                    "CacheControl": "max-age=86400",  # 1 day cache
                },
                "signature_version": "s3v4",
                "addressing_style": "path" if _endpoint_url else "auto",  # Path style for R2
            }
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    # For signed URLs (private files)
    AWS_S3_SIGNATURE_VERSION = 's3v4'
    AWS_QUERYSTRING_AUTH = True
    AWS_QUERYSTRING_EXPIRE = 3600  # 1 hour signed URL expiry
    
    # Log storage configuration
    print(f"[STORAGE] Using S3-compatible storage: {_bucket_name}")
else:
    # Local file storage - WARNING: Files lost on Railway redeploy!
    # To persist files, either:
    # 1. Configure S3/R2 storage (recommended)
    # 2. Attach a Railway Volume at /app/media
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
    
    if os.environ.get('RAILWAY_ENVIRONMENT'):
        print("[STORAGE] WARNING: Using local storage on Railway - files will be lost on redeploy!")
        print("[STORAGE] Set STORAGE_TYPE=s3 or STORAGE_TYPE=r2 with credentials for persistence")

# ==============================================================================
# CACHE & SESSION - Database-backed for persistence
# ==============================================================================
# Use database cache to persist across redeploys (no Redis needed)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'django_cache_table',
    }
}

# Session Configuration - Database-backed for persistence across deployments
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30  # 30 days
SESSION_COOKIE_SECURE = not DEBUG  # HTTPS only in production
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_SAVE_EVERY_REQUEST = True  # Refresh session on each request

# CSRF Cookie settings
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True

# ==============================================================================
# CELERY - Run tasks synchronously (no Redis/worker needed)
# ==============================================================================
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# ==============================================================================
# OTHER SETTINGS
# ==============================================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==============================================================================
# EMAIL CONFIGURATION (for OTP)
# ==============================================================================
# Console backend for development/testing - prints emails to logs
# For production, configure SMTP/SES with environment variables
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@hamsvic.com')

# ==============================================================================
# TWILIO SMS CONFIGURATION (for OTP)
# ==============================================================================
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# Security for production
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_TRUSTED_ORIGINS = ['https://*.railway.app', 'https://*.up.railway.app']

# ==============================================================================
# AUTHENTICATION SETTINGS
# ==============================================================================
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# ==============================================================================
# MODULE ACCESS CONFIGURATION
# ==============================================================================

# URL patterns that require specific module subscriptions
MODULE_PROTECTED_URLS = {
    'new_estimate': [
        r'^/datas/',
        r'^/groups/',
        r'^/items/',
        r'^/fetch-item/',
    ],
    'temp_works': [
        r'^/tempworks/',
        r'^/temp-groups/',
        r'^/temp-items/',
        r'^/temp-rate/',
    ],
    'estimate': [
        r'^/estimate/',
        r'^/projects/',
    ],
    'workslip': [
        r'^/workslip/',
    ],
    'bill': [
        r'^/bill/',
    ],
    'self_formatted': [
        r'^/self-formatted/',
    ],
    'amc': [
        r'^/amc/',
    ],
}

# URLs exempt from module access checks
MODULE_EXEMPT_URLS = [
    r'^/accounts/',
    r'^/admin/',
    r'^/admin-panel/',
    r'^/static/',
    r'^/media/',
    r'^/$',
    r'^/api/auth/',
    r'^/pricing/',
    r'^/help/',
    r'^/support/',
    r'^/dashboard/',
    r'^/my-subscription/',
    r'^/profile/',
    r'^/subscriptions/',
    r'^/saved-works/',
    r'^/health/',
]

# URLs that track usage (for metered billing)
USAGE_TRACKED_URLS = [
    (r'^/estimate/$', 'estimate', 'POST'),
    (r'^/workslip/$', 'workslip', 'POST'),
    (r'^/bill/$', 'bill', 'POST'),
    (r'^/self-formatted/use/$', 'self_formatted', 'POST'),
]

# ==============================================================================
# RAZORPAY PAYMENT GATEWAY
# ==============================================================================
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET', '')
