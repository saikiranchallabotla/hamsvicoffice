"""
Safe Data Restoration Script
=============================
Restores data from SQLite to PostgreSQL using Django ORM.
"""

import os
import sys
import sqlite3
import django
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'estimate_site.settings')
os.environ['DB_ENGINE'] = 'postgresql'

sys.path.insert(0, str(Path(__file__).parent))
django.setup()

from django.db import connection, transaction
from django.contrib.auth.models import User

def restore_states():
    """Restore states from SQLite to PostgreSQL"""
    from datasets.models import State
    
    sqlite_conn = sqlite3.connect('db.sqlite3')
    cursor = sqlite_conn.cursor()
    
    cursor.execute('SELECT * FROM datasets_state')
    rows = cursor.fetchall()
    
    print(f"\n📍 Restoring {len(rows)} States...")
    
    for row in rows:
        id, code, name, full_name, display_order, flag_icon, is_active, is_default, created, updated = row
        
        state, created_flag = State.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'full_name': full_name,
                'display_order': display_order,
                'flag_icon': flag_icon,
                'is_active': bool(is_active),
                'is_default': bool(is_default),
            }
        )
        status = "Created" if created_flag else "Updated"
        print(f"   ✓ {status}: {state.name} ({state.code})")
    
    sqlite_conn.close()
    return len(rows)

def restore_modules():
    """Restore subscription modules from SQLite to PostgreSQL"""
    from subscriptions.models import Module
    
    sqlite_conn = sqlite3.connect('db.sqlite3')
    cursor = sqlite_conn.cursor()
    
    cursor.execute('SELECT * FROM subscriptions_module')
    rows = cursor.fetchall()
    
    # Get column names
    cursor.execute('PRAGMA table_info(subscriptions_module)')
    columns = [col[1] for col in cursor.fetchall()]
    
    print(f"\n📦 Restoring {len(rows)} Modules...")
    
    for row in rows:
        data = dict(zip(columns, row))
        
        module, created = Module.objects.update_or_create(
            code=data.get('code', data.get('name', '').lower().replace(' ', '-')),
            defaults={
                'name': data.get('name', ''),
                'description': data.get('description', ''),
                'icon': data.get('icon', ''),
                'is_active': bool(data.get('is_active', 1)),
                'is_free': bool(data.get('is_free', 0)),
                'is_addon': bool(data.get('is_addon', 0)),
                'display_order': data.get('display_order', 0),
                'url_name': data.get('url_name', ''),
            }
        )
        status = "Created" if created else "Updated"
        print(f"   ✓ {status}: {module.name}")
    
    sqlite_conn.close()
    return len(rows)

def restore_module_backends():
    """Restore module backends from SQLite to PostgreSQL"""
    from subscriptions.models import Module, ModuleBackend
    
    sqlite_conn = sqlite3.connect('db.sqlite3')
    cursor = sqlite_conn.cursor()
    
    cursor.execute('SELECT * FROM subscriptions_modulebackend')
    rows = cursor.fetchall()
    
    cursor.execute('PRAGMA table_info(subscriptions_modulebackend)')
    columns = [col[1] for col in cursor.fetchall()]
    
    print(f"\n⚙️ Restoring {len(rows)} Module Backends...")
    
    for row in rows:
        data = dict(zip(columns, row))
        
        # Get the module by ID from the new PostgreSQL database
        try:
            # First get module code from SQLite
            cursor.execute(f"SELECT code FROM subscriptions_module WHERE id = ?", (data['module_id'],))
            module_code = cursor.fetchone()
            if module_code:
                module = Module.objects.get(code=module_code[0])
            else:
                print(f"   ⚠ Skipping backend - module_id {data['module_id']} not found in SQLite")
                continue
        except Module.DoesNotExist:
            print(f"   ⚠ Skipping backend - module code {module_code[0]} not found in PostgreSQL")
            continue
        
        backend, created = ModuleBackend.objects.update_or_create(
            module=module,
            code=data.get('code', '') or data.get('name', '').lower().replace(' ', '_'),
            defaults={
                'category': data.get('category', 'civil'),
                'name': data.get('name', ''),
                'description': data.get('description', ''),
                'file': data.get('file', ''),
                'is_default': bool(data.get('is_default', 0)),
                'is_active': bool(data.get('is_active', 1)),
                'display_order': data.get('display_order', 0),
            }
        )
        status = "Created" if created else "Updated"
        print(f"   ✓ {status}: {backend.name}")
    
    sqlite_conn.close()
    return len(rows)

def restore_module_pricing():
    """Restore module pricing from SQLite to PostgreSQL"""
    from subscriptions.models import Module, ModulePricing
    
    sqlite_conn = sqlite3.connect('db.sqlite3')
    cursor = sqlite_conn.cursor()
    
    cursor.execute('SELECT * FROM subscriptions_modulepricing')
    rows = cursor.fetchall()
    
    cursor.execute('PRAGMA table_info(subscriptions_modulepricing)')
    columns = [col[1] for col in cursor.fetchall()]
    
    print(f"\n💰 Restoring {len(rows)} Module Pricing Plans...")
    
    for row in rows:
        data = dict(zip(columns, row))
        
        # Get module code from SQLite and find in PostgreSQL
        try:
            cursor.execute(f"SELECT code FROM subscriptions_module WHERE id = ?", (data['module_id'],))
            module_code = cursor.fetchone()
            if module_code:
                module = Module.objects.get(code=module_code[0])
            else:
                print(f"   ⚠ Skipping pricing - module_id {data['module_id']} not found in SQLite")
                continue
        except Module.DoesNotExist:
            print(f"   ⚠ Skipping pricing - module code not found in PostgreSQL")
            continue
        
        pricing, created = ModulePricing.objects.update_or_create(
            module=module,
            duration_months=data.get('duration_months', 1),
            defaults={
                'base_price': data.get('base_price', 0),
                'sale_price': data.get('sale_price', 0),
                'gst_percent': data.get('gst_percent', 18),
                'usage_limit': data.get('usage_limit', 0),
                'is_active': bool(data.get('is_active', 1)),
                'is_popular': bool(data.get('is_popular', 0)),
            }
        )
        status = "Created" if created else "Updated"
        print(f"   ✓ {status}: {module.name} - {pricing.duration_months} months")
    
    sqlite_conn.close()
    return len(rows)

def restore_organizations():
    """Restore organizations from SQLite to PostgreSQL"""
    from core.models import Organization
    
    sqlite_conn = sqlite3.connect('db.sqlite3')
    cursor = sqlite_conn.cursor()
    
    cursor.execute('SELECT * FROM core_organization')
    rows = cursor.fetchall()
    
    cursor.execute('PRAGMA table_info(core_organization)')
    columns = [col[1] for col in cursor.fetchall()]
    
    print(f"\n🏢 Restoring {len(rows)} Organizations...")
    
    for row in rows:
        data = dict(zip(columns, row))
        
        org, created = Organization.objects.update_or_create(
            name=data.get('name', ''),
            defaults={
                'description': data.get('description', ''),
            }
        )
        status = "Created" if created else "Updated"
        print(f"   ✓ {status}: {org.name}")
    
    sqlite_conn.close()
    return len(rows)

def restore_jobs():
    """Restore jobs from SQLite to PostgreSQL"""
    from core.models import Job
    
    sqlite_conn = sqlite3.connect('db.sqlite3')
    cursor = sqlite_conn.cursor()
    
    cursor.execute('SELECT * FROM core_job')
    rows = cursor.fetchall()
    
    cursor.execute('PRAGMA table_info(core_job)')
    columns = [col[1] for col in cursor.fetchall()]
    
    print(f"\n📋 Restoring {len(rows)} Jobs...")
    
    restored = 0
    for row in rows:
        data = dict(zip(columns, row))
        
        # Get user if exists
        user = None
        if data.get('user_id'):
            try:
                user = User.objects.get(id=data['user_id'])
            except User.DoesNotExist:
                print(f"   ⚠ Skipping job - user_id {data['user_id']} not found")
                continue
        
        try:
            job, created = Job.objects.update_or_create(
                job_number=data.get('job_number', ''),
                defaults={
                    'name': data.get('name', ''),
                    'status': data.get('status', 'pending'),
                    'user': user,
                }
            )
            status = "Created" if created else "Updated"
            print(f"   ✓ {status}: Job {job.job_number}")
            restored += 1
        except Exception as e:
            print(f"   ⚠ Error with job {data.get('job_number')}: {e}")
    
    sqlite_conn.close()
    return restored

def main():
    print("=" * 70)
    print("DATA RESTORATION: SQLite → PostgreSQL (Neon)")
    print("=" * 70)
    
    total = 0
    
    # Restore in order (respecting foreign keys)
    total += restore_states()
    total += restore_modules()
    total += restore_module_backends()
    total += restore_module_pricing()
    total += restore_organizations()
    # total += restore_jobs()  # Uncomment if needed
    
    print("\n" + "=" * 70)
    print(f"✅ RESTORATION COMPLETE! {total} records processed")
    print("=" * 70)

if __name__ == '__main__':
    main()
