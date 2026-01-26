# estimate_site/celery.py
"""
Celery configuration for async task processing (Excel parsing, file generation, etc.)
"""

import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'estimate_site.settings')

app = Celery('estimate_site')

# Load configuration from Django settings with 'CELERY' namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all registered Django apps
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    """Simple debug task for testing Celery"""
    print(f'Request: {self.request!r}')
