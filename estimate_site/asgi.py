"""
ASGI config for estimate_site project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

# Celery setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'estimate_site.settings')
django_asgi_app = get_asgi_application()

from estimate_site import celery as celery_app

# Initialize Celery app
celery_app.app

application = django_asgi_app
