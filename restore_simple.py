"""
Simple Data Restoration Script - Batch Mode
============================================
Restores data using bulk operations for faster execution.
"""

import os
import sys
import sqlite3
import django
from pathlib import Path
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'estimate_site.settings')
os.environ['DB_ENGINE'] = 'postgresql'

sys.path.insert(0, str(Path(__file__).parent))
django.setup()

from django.db import transaction

def restore_all():
    """Restore all data in one transaction"""
    
    print("=" * 70)
    print("DATA RESTORATION: SQLite → PostgreSQL (Neon)")
    print("=" * 70)
    
    sqlite_conn = sqlite3.connect('db.sqlite3')
    sqlite_conn.row_factory = sqlite3.Row
    cursor = sqlite_conn.cursor()
    
    # Import models
    from datasets.models import State
    from subscriptions.models import Module, ModuleBackend, ModulePricing
    from core.models import Organization
    
    with transaction.atomic():
        # 1. Restore States
        print("\n📍 Restoring States...")
        cursor.execute('SELECT * FROM datasets_state')
        for row in cursor.fetchall():
            State.objects.update_or_create(
                code=row['code'],
                defaults={
                    'name': row['name'],
                    'full_name': row['full_name'],
                    'display_order': row['display_order'],
                    'flag_icon': row['flag_icon'],
                    'is_active': bool(row['is_active']),
                    'is_default': bool(row['is_default']),
                }
            )
            print(f"   ✓ {row['name']}")
        
        # 2. Restore Modules  
        print("\n📦 Restoring Modules...")
        cursor.execute('SELECT * FROM subscriptions_module')
        module_id_map = {}  # SQLite ID -> PostgreSQL object
        
        for row in cursor.fetchall():
            module, _ = Module.objects.update_or_create(
                code=row['code'],
                defaults={
                    'name': row['name'],
                    'description': row['description'] or '',
                    'icon': row['icon'] or '',
                    'color': row['color'] or '#3B82F6',
                    'display_order': row['display_order'],
                    'is_active': bool(row['is_active']),
                    'is_free': bool(row['is_free']),
                    'is_addon': bool(row['is_addon']),
                    'trial_days': row['trial_days'],
                    'free_tier_limit': row['free_tier_limit'],
                    'url_name': row['url_name'] or '',
                    'backend_sheet_name': row['backend_sheet_name'] or '',
                    'backend_sheet_file': row['backend_sheet_file'] or '',
                }
            )
            module_id_map[row['id']] = module
            print(f"   ✓ {row['name']}")
        
        # 3. Restore Module Backends
        print("\n⚙️ Restoring Module Backends...")
        cursor.execute('SELECT * FROM subscriptions_modulebackend')
        
        for row in cursor.fetchall():
            sqlite_module_id = row['module_id']
            if sqlite_module_id not in module_id_map:
                print(f"   ⚠ Skipping backend - module_id {sqlite_module_id} not found")
                continue
            
            module = module_id_map[sqlite_module_id]
            
            # Generate a unique code if not present
            code = row['code'] or row['name'].lower().replace(' ', '_').replace('.', '')[:50]
            
            ModuleBackend.objects.update_or_create(
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
            print(f"   ✓ {row['name']}")
        
        # 4. Restore Module Pricing
        print("\n💰 Restoring Module Pricing...")
        cursor.execute('SELECT * FROM subscriptions_modulepricing')
        
        for row in cursor.fetchall():
            sqlite_module_id = row['module_id']
            if sqlite_module_id not in module_id_map:
                print(f"   ⚠ Skipping pricing - module_id {sqlite_module_id} not found")
                continue
            
            module = module_id_map[sqlite_module_id]
            
            ModulePricing.objects.update_or_create(
                module=module,
                duration_months=row['duration_months'],
                defaults={
                    'base_price': Decimal(str(row['base_price'])),
                    'sale_price': Decimal(str(row['sale_price'])) if row['sale_price'] else None,
                    'gst_percent': Decimal(str(row['gst_percent'])),
                    'usage_limit': row['usage_limit'],
                    'is_active': bool(row['is_active']),
                    'is_popular': bool(row['is_popular']),
                }
            )
            print(f"   ✓ {module.name} - {row['duration_months']} months")
        
        # 5. Restore Organizations
        print("\n🏢 Restoring Organizations...")
        cursor.execute('SELECT * FROM core_organization')
        
        for row in cursor.fetchall():
            Organization.objects.update_or_create(
                name=row['name'],
                defaults={
                    'description': row['description'] or '',
                }
            )
            print(f"   ✓ {row['name']}")
    
    sqlite_conn.close()
    
    print("\n" + "=" * 70)
    print("✅ RESTORATION COMPLETE!")
    print("=" * 70)

if __name__ == '__main__':
    restore_all()
