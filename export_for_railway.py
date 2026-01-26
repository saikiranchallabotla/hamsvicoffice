"""
Export local SQLite data to JSON fixtures for Railway PostgreSQL migration.
Run locally: python export_for_railway.py
Then commit the fixtures and deploy.
"""
import os
import sys
import json
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'estimate_site.settings')
django.setup()

from django.core import serializers
from subscriptions.models import Module, ModulePricing, ModuleBackend
from datasets.models import State

def export_fixtures():
    """Export key data as Django fixtures."""
    
    fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures')
    os.makedirs(fixtures_dir, exist_ok=True)
    
    # Export Modules
    modules = Module.objects.all()
    with open(os.path.join(fixtures_dir, 'modules.json'), 'w') as f:
        data = serializers.serialize('json', modules, indent=2)
        f.write(data)
    print(f"Exported {modules.count()} modules")
    
    # Export Module Pricing
    pricing = ModulePricing.objects.all()
    with open(os.path.join(fixtures_dir, 'module_pricing.json'), 'w') as f:
        data = serializers.serialize('json', pricing, indent=2)
        f.write(data)
    print(f"Exported {pricing.count()} pricing options")
    
    # Export Module Backends
    backends = ModuleBackend.objects.all()
    with open(os.path.join(fixtures_dir, 'module_backends.json'), 'w') as f:
        data = serializers.serialize('json', backends, indent=2)
        f.write(data)
    print(f"Exported {backends.count()} backends")
    
    # Export States
    states = State.objects.all()
    with open(os.path.join(fixtures_dir, 'states.json'), 'w', encoding='utf-8') as f:
        data = serializers.serialize('json', states, indent=2)
        f.write(data)
    print(f"Exported {states.count()} states")
    
    print(f"\nFixtures saved to: {fixtures_dir}")
    print("Commit these files and deploy to Railway.")
    print("Then run: python manage.py loaddata modules module_pricing module_backends states")


if __name__ == '__main__':
    export_fixtures()
