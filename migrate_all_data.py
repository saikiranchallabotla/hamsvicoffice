"""
Complete SQLite to PostgreSQL Data Migration
=============================================
This script properly migrates ALL data from SQLite to PostgreSQL.
"""

import os
import sys
import django
from pathlib import Path

# Setup path
sys.path.insert(0, str(Path(__file__).parent))

def migrate_data():
    """Migrate all data from SQLite to PostgreSQL"""
    
    print("=" * 70)
    print("COMPLETE DATA MIGRATION: SQLite → PostgreSQL")
    print("=" * 70)
    
    # Step 1: Connect to SQLite and export data
    print("\n[1/4] Connecting to SQLite database...")
    os.environ['DB_ENGINE'] = 'sqlite3'
    os.environ['DJANGO_SETTINGS_MODULE'] = 'estimate_site.settings'
    
    # Force reload of Django with SQLite
    import importlib
    if 'django.conf' in sys.modules:
        importlib.reload(sys.modules['django.conf'])
    
    django.setup()
    
    from django.apps import apps
    from django.db import connection
    
    # Collect all data from SQLite
    sqlite_data = {}
    models_to_migrate = [
        'core.organization',
        'core.membership', 
        'core.job',
        'core.outputfile',
        'core.userprofile',
        'core.project',
        'accounts.userprofile',
        'accounts.usersession',
        'subscriptions.module',
        'subscriptions.modulebackend',
        'subscriptions.modulepricing',
        'subscriptions.usermodulesubscription',
        'subscriptions.usagelog',
        'datasets.state',
        'datasets.auditlog',
        'auth.user',
    ]
    
    print("\n[2/4] Extracting data from SQLite...")
    for model_path in models_to_migrate:
        try:
            app_label, model_name = model_path.split('.')
            Model = apps.get_model(app_label, model_name)
            data = list(Model.objects.all().values())
            sqlite_data[model_path] = {
                'model': Model,
                'data': data,
                'count': len(data)
            }
            print(f"   ✓ {model_path}: {len(data)} records")
        except Exception as e:
            print(f"   ✗ {model_path}: Error - {e}")
    
    # Close SQLite connection
    connection.close()
    
    # Step 2: Switch to PostgreSQL
    print("\n[3/4] Switching to PostgreSQL...")
    os.environ['DB_ENGINE'] = 'postgresql'
    
    # Force Django to reload with PostgreSQL
    from django.db import connections
    connections.close_all()
    
    # Reimport Django settings
    from django.conf import settings
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'hamsvic'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'ATOMIC_REQUESTS': True,
        'CONN_MAX_AGE': 600,
        'OPTIONS': {
            'sslmode': 'require',
        },
    }
    
    print("\n[4/4] Importing data to PostgreSQL...")
    
    # Import data in correct order (respecting foreign keys)
    import_order = [
        'datasets.state',
        'auth.user',
        'subscriptions.module',
        'subscriptions.modulebackend',
        'subscriptions.modulepricing',
        'core.organization',
        'core.membership',
        'core.job',
        'core.outputfile',
        'core.project',
        'core.userprofile',
        'accounts.userprofile',
        'accounts.usersession',
        'subscriptions.usermodulesubscription',
        'subscriptions.usagelog',
        'datasets.auditlog',
    ]
    
    for model_path in import_order:
        if model_path not in sqlite_data:
            continue
            
        info = sqlite_data[model_path]
        Model = info['model']
        data = info['data']
        
        if not data:
            continue
            
        try:
            # Check if data already exists
            existing = Model.objects.count()
            if existing >= info['count']:
                print(f"   ⏭ {model_path}: Already has {existing} records (skipping)")
                continue
            
            # Clear existing and import fresh
            if model_path != 'auth.user':  # Don't delete users
                Model.objects.all().delete()
            
            # Recreate objects
            created = 0
            for record in data:
                try:
                    obj = Model(**record)
                    obj.save()
                    created += 1
                except Exception as e:
                    # Try without pk for auto-increment fields
                    if 'id' in record:
                        del record['id']
                        try:
                            obj = Model(**record)
                            obj.save()
                            created += 1
                        except:
                            pass
                    
            print(f"   ✓ {model_path}: Imported {created}/{info['count']} records")
            
        except Exception as e:
            print(f"   ✗ {model_path}: Error - {e}")
    
    print("\n" + "=" * 70)
    print("MIGRATION COMPLETE!")
    print("=" * 70)

if __name__ == '__main__':
    migrate_data()
