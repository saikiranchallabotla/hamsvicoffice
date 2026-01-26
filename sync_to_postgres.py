"""
Sync SQLite data to PostgreSQL
This will make PostgreSQL match SQLite (SQLite is the source of truth)
"""
import os
import sqlite3

os.environ['DJANGO_SETTINGS_MODULE'] = 'estimate_site.settings'
os.environ['DB_ENGINE'] = 'postgresql'

import django
django.setup()

from django.db import transaction
from datasets.models import State
from subscriptions.models import Module, ModuleBackend, ModulePricing
from core.models import Organization

print("=" * 60)
print("SYNCING: SQLite → PostgreSQL")
print("=" * 60)

sqlite_conn = sqlite3.connect('db.sqlite3')
sqlite_conn.row_factory = sqlite3.Row
cursor = sqlite_conn.cursor()

# Sync Organizations
print("\n🏢 Syncing Organizations...")
cursor.execute('SELECT * FROM core_organization')
for row in cursor.fetchall():
    org, created = Organization.objects.update_or_create(
        name=row['name'],
        defaults={
            'slug': row['slug'] or '',
            'is_active': bool(row['is_active']),
        }
    )
    print(f"  {'Created' if created else 'Updated'}: {org.name}")

# Sync Module Pricing (clear and re-add to avoid duplicates)
print("\n💰 Syncing Module Pricing...")
cursor.execute('''
    SELECT mp.*, m.code as module_code 
    FROM subscriptions_modulepricing mp 
    JOIN subscriptions_module m ON mp.module_id = m.id
''')

# Get all modules from PostgreSQL
pg_modules = {m.code: m for m in Module.objects.all()}

# Clear existing pricing and re-add
ModulePricing.objects.all().delete()
print("  Cleared existing pricing...")

for row in cursor.fetchall():
    module = pg_modules.get(row['module_code'])
    if module:
        pricing = ModulePricing.objects.create(
            module=module,
            duration_months=row['duration_months'],
            base_price=row['base_price'],
            sale_price=row['sale_price'] if row['sale_price'] else None,
            gst_percent=row['gst_percent'],
            usage_limit=row['usage_limit'],
            is_active=bool(row['is_active']),
            is_popular=bool(row['is_popular']),
        )
        print(f"  Created: {module.name} - {row['duration_months']} months")

sqlite_conn.close()

print("\n" + "=" * 60)
print("✅ SYNC COMPLETE!")
print("=" * 60)
print("\nNow run 'python compare_databases.py' to verify.")
