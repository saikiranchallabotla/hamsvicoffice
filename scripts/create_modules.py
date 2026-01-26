"""
Script to create the required modules in the database.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'estimate_site.settings')
django.setup()

from subscriptions.models import Module

modules_data = [
    {
        'code': 'new_estimate',
        'name': 'New Estimate',
        'description': 'Create new estimates by selecting items from the database',
        'icon': 'plus-circle',
        'display_order': 1,
        'trial_days': 1,
        'url_name': 'datas',
    },
    {
        'code': 'temp_works',
        'name': 'Temporary Works',
        'description': 'Prepare temporary lighting and hiring estimates',
        'icon': 'lightbulb',
        'display_order': 2,
        'trial_days': 1,
        'url_name': 'tempworks_home',
    },
    {
        'code': 'estimate',
        'name': 'Estimate',
        'description': 'Create detailed project estimates with material and labor calculations',
        'icon': 'calculator',
        'display_order': 3,
        'trial_days': 1,
        'url_name': 'estimate',
    },
    {
        'code': 'workslip',
        'name': 'Work Slip',
        'description': 'Generate work slips and measurement sheets',
        'icon': 'clipboard-check',
        'display_order': 4,
        'trial_days': 1,
        'url_name': 'workslip',
    },
    {
        'code': 'bill',
        'name': 'Bill',
        'description': 'Create and manage bills for completed work',
        'icon': 'receipt',
        'display_order': 5,
        'trial_days': 1,
        'url_name': 'bill',
    },
    {
        'code': 'self_formatted',
        'name': 'Self Formatted',
        'description': 'Create custom formatted documents with your own templates',
        'icon': 'file-earmark-text',
        'display_order': 6,
        'trial_days': 1,
        'url_name': 'self_formatted',
    },
]

for data in modules_data:
    module, created = Module.objects.update_or_create(
        code=data['code'],
        defaults=data
    )
    if created:
        print(f"Created module: {module.name}")
    else:
        print(f"Updated module: {module.name}")

print("\nDone! All modules created.")
