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
SECRET_KEY = os.environ.get('SECRET_KEY', 'railway-pilot-secret-key-change-in-production')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = ['*']  # Railway handles this at proxy level

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
        'DIRS': [],
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
# DATABASE - Railway PostgreSQL
# ==============================================================================
DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(default=DATABASE_URL, conn_max_age=600)
    }
else:
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
# For pilot: Use local storage (files lost on redeploy)
# For production: Configure S3/DO Spaces with environment variables
STORAGE_TYPE = os.environ.get('STORAGE_TYPE', 'local')

if STORAGE_TYPE == 's3':
    # AWS S3 or DO Spaces (S3-compatible)
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "access_key": os.environ.get('AWS_ACCESS_KEY_ID', ''),
                "secret_key": os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
                "bucket_name": os.environ.get('AWS_STORAGE_BUCKET_NAME', 'hamsvic'),
                "region_name": os.environ.get('AWS_S3_REGION_NAME', 'us-east-1'),
                "endpoint_url": os.environ.get('AWS_S3_ENDPOINT_URL', None),
                "default_acl": "private",
                "file_overwrite": False,
            }
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    AWS_S3_SIGNATURE_VERSION = 's3v4'
    AWS_QUERYSTRING_AUTH = True
    AWS_QUERYSTRING_EXPIRE = 3600
else:
    # Local file storage (pilot mode - files may be lost on redeploy!)
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

# ==============================================================================
# CACHE & SESSION - Simple in-memory (no Redis needed)
# ==============================================================================
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

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
