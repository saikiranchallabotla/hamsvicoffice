"""Restore Module Backends"""
import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'estimate_site.settings'
os.environ['DB_ENGINE'] = 'postgresql'

import django
django.setup()

import sqlite3
from subscriptions.models import Module, ModuleBackend

sqlite_conn = sqlite3.connect('db.sqlite3')
sqlite_conn.row_factory = sqlite3.Row
cursor = sqlite_conn.cursor()

# Get modules from PostgreSQL with their codes
pg_modules = {m.code: m for m in Module.objects.all()}
print('PostgreSQL modules:', list(pg_modules.keys()))

# Get backends from SQLite
cursor.execute('''
    SELECT mb.*, m.code as module_code 
    FROM subscriptions_modulebackend mb 
    JOIN subscriptions_module m ON mb.module_id = m.id
''')

for row in cursor.fetchall():
    print(f"Backend: {row['name']} -> Module: {row['module_code']}")
    module = pg_modules.get(row['module_code'])
    if module:
        code = row['code'] or row['name'].lower().replace(' ', '_').replace('.', '')[:50]
        backend, created = ModuleBackend.objects.update_or_create(
            module=module,
            code=code,
            defaults={
                'category': row['category'] or 'civil',
                'name': row['name'],
                'description': row['description'] or '',
                'file': row['file'] or '',
                'is_default': bool(row['is_default']),
                'is_active': bool(row['is_active']),
                'display_order': row['display_order'],
            }
        )
        print(f"  -> {'Created' if created else 'Updated'}")

print(f"\nDone! Backends: {ModuleBackend.objects.count()}")
