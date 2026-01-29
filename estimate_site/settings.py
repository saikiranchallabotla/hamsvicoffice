from pathlib import Path
import os
import sys
from dotenv import load_dotenv

# Increase recursion limit for Python 3.14 compatibility with Django templates
sys.setrecursionlimit(5000)

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ==============================================================================
# SECURITY SETTINGS (ENVIRONMENT-BASED)
# ==============================================================================

# Load from .env; fall back to insecure default for development only
SECRET_KEY = os.getenv(
    'DJANGO_SECRET_KEY',
    'django-insecure-vhzmf%h+a(#4)k&g5da9oa8kx)1ffancns=x^qo2u=p28!+xjx'
)

DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')

# ==============================================================================
# HTTPS/SSL SECURITY (Production only)
# ==============================================================================
if not DEBUG:
    # Force HTTPS
    SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'True') == 'True'
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    # Secure cookies
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
    # HSTS (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Additional security headers
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'


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
    'django_celery_beat',  # Celery beat scheduler (optional)

    # Local apps
    'core',
    'accounts',  # User accounts, OTP auth, profiles, sessions
    'subscriptions',  # Module subscriptions, payments, invoices
    'datasets',  # Admin-managed SSR data, versioning, imports
    'support',  # Help center, FAQs, tickets, announcements
    'admin_panel',  # Custom admin panel for SaaS management
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Serve static files
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.OrganizationMiddleware',
    
    # Session & Subscription Middleware
    'accounts.middleware.SessionTrackingMiddleware',
    'accounts.middleware.ConcurrentSessionCheckMiddleware',  # Check if session was kicked
    'subscriptions.middleware.SubscriptionCacheMiddleware',
    'subscriptions.middleware.ModuleAccessMiddleware',
    'subscriptions.middleware.UsageTrackingMiddleware',
]

# Maximum concurrent sessions per user (like Netflix/Prime)
# User will be logged out from oldest device when limit exceeded
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
# DATABASE CONFIGURATION
# ==============================================================================
# Supports DATABASE_URL (Railway/Heroku), individual vars, or SQLite

import dj_database_url

DATABASE_URL = os.getenv('DATABASE_URL', '')
DB_ENGINE = os.getenv('DB_ENGINE', 'sqlite3')

if DATABASE_URL:
    # Railway, Heroku, Render - auto-configure from DATABASE_URL
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
elif DB_ENGINE == 'postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'hamsvic'),
            'USER': os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
            'ATOMIC_REQUESTS': True,  # Each request is a transaction
            'CONN_MAX_AGE': 600,  # Connection pooling
            'OPTIONS': {
                'sslmode': 'require',  # Required for Neon and cloud PostgreSQL
            },
        }
    }
else:
    # Default: SQLite for local development
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# ==============================================================================
# FILE STORAGE CONFIGURATION
# ==============================================================================
# Local storage for development, S3/R2/DO Spaces for production
# 
# ⚠️ IMPORTANT: Without cloud storage, user uploads are LOST on each redeploy!
# Set STORAGE_TYPE=s3 or STORAGE_TYPE=r2 in Railway environment variables.

STORAGE_TYPE = os.getenv('STORAGE_TYPE', 'local')

if STORAGE_TYPE in ('s3', 'r2'):
    # AWS S3, Cloudflare R2, or DigitalOcean Spaces (all S3-compatible)
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "access_key": os.getenv('AWS_ACCESS_KEY_ID', ''),
                "secret_key": os.getenv('AWS_SECRET_ACCESS_KEY', ''),
                "bucket_name": os.getenv('AWS_STORAGE_BUCKET_NAME', 'hamsvic'),
                "region_name": os.getenv('AWS_S3_REGION_NAME', 'us-east-1'),
                # For DO Spaces or custom S3 endpoint:
                "endpoint_url": os.getenv('AWS_S3_ENDPOINT_URL', None),
                "default_acl": "private",  # Files are private by default
                "file_overwrite": False,
            }
        },
        "staticfiles": {
            "BACKEND": "storages.backends.s3boto3.S3StaticStorage",
            "OPTIONS": {
                "access_key": os.getenv('AWS_ACCESS_KEY_ID', ''),
                "secret_key": os.getenv('AWS_SECRET_ACCESS_KEY', ''),
                "bucket_name": os.getenv('AWS_STORAGE_BUCKET_NAME', 'hamsvic'),
                "region_name": os.getenv('AWS_S3_REGION_NAME', 'us-east-1'),
                "endpoint_url": os.getenv('AWS_S3_ENDPOINT_URL', None),
                "default_acl": "public-read",
            }
        },
    }
    AWS_S3_SIGNATURE_VERSION = 's3v4'
    AWS_QUERYSTRING_AUTH = True  # Signed URLs for private files
    AWS_QUERYSTRING_EXPIRE = 3600  # URLs valid for 1 hour
else:
    # Local file storage (development) + WhiteNoise for production
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'
    STATIC_URL = 'static/'
    STATIC_ROOT = BASE_DIR / 'staticfiles'
    
    # WhiteNoise for serving static files in production without S3
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }


# ==============================================================================
# CELERY CONFIGURATION
# ==============================================================================

# For development: Run tasks synchronously without needing Redis/RabbitMQ
# Set to False in production when you have a proper Celery worker setup
CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', 'True').lower() == 'true'
CELERY_TASK_EAGER_PROPAGATES = True  # Propagate exceptions in eager mode

# Celery broker (message queue) - only needed when CELERY_TASK_ALWAYS_EAGER is False
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
# Celery result backend (task results storage)
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

# Celery configuration
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes soft limit (for graceful shutdown)

# Task routes (optional: specify which workers handle which tasks)
CELERY_TASK_ROUTES = {
    'core.tasks.process_excel_upload': {'queue': 'excel_processing'},
    'core.tasks.generate_bill': {'queue': 'excel_processing'},
    'core.tasks.generate_workslip': {'queue': 'excel_processing'},
}


# ==============================================================================
# CACHE & SESSION CONFIGURATION
# ==============================================================================

# Use local memory cache for development (no Redis required)
# Switch to Redis in production by setting REDIS_URL environment variable
REDIS_URL = os.getenv('REDIS_URL', '')

if REDIS_URL:
    # Production: Use Redis
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            }
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'
else:
    # Development: Use local memory cache
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-snowflake',
        }
    }
    # Use database sessions for development
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'


# ==============================================================================
# PASSWORD VALIDATION
# ==============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# ==============================================================================
# INTERNATIONALIZATION
# ==============================================================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'  # IST timezone
USE_I18N = True
USE_TZ = True


# ==============================================================================
# LOGGING CONFIGURATION
# ==============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
        'celery': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        },
        'core': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
        },
    },
}

# Ensure logs directory exists
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)


# ==============================================================================
# DEFAULT PRIMARY KEY
# ==============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


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
}

# URLs exempt from module access checks
MODULE_EXEMPT_URLS = [
    r'^/accounts/',
    r'^/admin/',
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
    r'^/subscriptions/',  # Allow access to subscription/trial pages
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

RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', '')
RAZORPAY_WEBHOOK_SECRET = os.getenv('RAZORPAY_WEBHOOK_SECRET', '')


# ==============================================================================
# TWILIO SMS CONFIGURATION
# ==============================================================================

TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '')  # Format: +1234567890


# ==============================================================================
# EMAIL CONFIGURATION
# ==============================================================================

EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'Hamsvic <noreply@hamsvic.com>')
