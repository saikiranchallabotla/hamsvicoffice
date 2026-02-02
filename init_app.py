"""
Startup initialization script - runs on every app start.
Ensures migrations, admin user, and modules are created.
"""
import os
import sys
import shutil
import django
from django.core.management import call_command

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'estimate_site.settings_railway')
django.setup()

from django.contrib.auth import get_user_model
from django.conf import settings
from accounts.models import UserProfile
from subscriptions.models import Module, ModulePricing

User = get_user_model()


def run_migrations():
    """Run Django migrations to set up database schema."""
    try:
        print('[INIT] Running migrations...')
        call_command('migrate', verbosity=0, interactive=False)
        print('[INIT] ✅ Migrations completed successfully')
    except Exception as e:
        print(f'[INIT] ⚠️  Migrations failed: {str(e)}')
        print('[INIT] Continuing with initialization...')


def create_admin():
    """Create or update admin user."""
    email = 'saikiranchallabotla@gmail.com'
    phone = '+916304911990'
    phone_alt = '6304911990'
    
    user = None
    
    # Find by email
    if User.objects.filter(email=email).exists():
        user = User.objects.get(email=email)
        print(f'[INIT] Found user by email: {email}')
    
    # Find by phone
    if not user:
        profile = UserProfile.objects.filter(phone__in=[phone, phone_alt]).first()
        if profile:
            user = profile.user
            print(f'[INIT] Found user by phone: {profile.phone}')
    
    if user:
        user.is_staff = True
        user.is_superuser = True
        if not user.email:
            user.email = email
        user.save()
        print(f'[INIT] User {user.username} updated to superuser!')
    else:
        user = User.objects.create_superuser(
            username='admin',
            email=email,
            password='Admin@123456',
            first_name='Saikiran',
            last_name='Challabotla',
        )
        print(f'[INIT] Superuser created: {email}')
    
    # Update profile
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.phone = phone
    profile.phone_verified = True
    profile.save()
    print(f'[INIT] Admin ready: {email} / {phone}')


def seed_modules():
    """Seed modules if not exist."""
    modules_data = [
        {'code': 'new_estimate', 'name': 'New Estimate', 'description': 'Create new estimates', 'url_name': 'datas', 'icon': 'file-earmark-plus', 'color': '#3B82F6', 'display_order': 1},
        {'code': 'estimate', 'name': 'Estimate', 'description': 'Manage estimates', 'url_name': 'estimate', 'icon': 'file-earmark-bar-graph', 'color': '#6366F1', 'display_order': 2},
        {'code': 'workslip', 'name': 'Workslip', 'description': 'Generate work slips', 'url_name': 'workslip', 'icon': 'clipboard-check', 'color': '#10B981', 'display_order': 3},
        {'code': 'bill', 'name': 'Bill', 'description': 'Create bills', 'url_name': 'bill', 'icon': 'receipt', 'color': '#F59E0B', 'display_order': 4},
        {'code': 'self_formatted', 'name': 'Self Formatted', 'description': 'Custom documents', 'url_name': 'self_formatted_form_page', 'icon': 'file-earmark-text', 'color': '#8B5CF6', 'display_order': 5},
        {'code': 'temp_works', 'name': 'Temporary Works', 'description': 'Temp project management', 'url_name': 'tempworks_home', 'icon': 'tools', 'color': '#EF4444', 'display_order': 6},
        {'code': 'amc', 'name': 'AMC', 'description': 'Annual Maintenance Contract', 'url_name': 'amc_home', 'icon': 'calendar-check', 'color': '#8B5CF6', 'display_order': 7},
    ]
    
    for data in modules_data:
        module, created = Module.objects.update_or_create(code=data['code'], defaults=data)
        # Add pricing
        for months, base, sale in [(1, 349, 299), (3, 899, 799), (6, 1699, 1499), (12, 2999, 2699)]:
            ModulePricing.objects.update_or_create(
                module=module, duration_months=months,
                defaults={'base_price': base, 'sale_price': sale}
            )
    
    print(f'[INIT] Created/Updated {len(modules_data)} modules with pricing')


def setup_database_cache():
    """Create the database cache table if using DatabaseCache backend."""
    from django.core.management import call_command
    from django.conf import settings
    from django.db import connection
    
    # Check if we're using DatabaseCache
    cache_backend = settings.CACHES.get('default', {}).get('BACKEND', '')
    if 'DatabaseCache' not in cache_backend:
        return
    
    cache_table = settings.CACHES.get('default', {}).get('LOCATION', 'django_cache_table')
    
    # Check if table exists
    with connection.cursor() as cursor:
        try:
            cursor.execute(f"SELECT 1 FROM {cache_table} LIMIT 1")
            print(f'[INIT] Cache table already exists: {cache_table}')
        except Exception:
            # Table doesn't exist, create it
            try:
                call_command('createcachetable', verbosity=0)
                print(f'[INIT] Created cache table: {cache_table}')
            except Exception as e:
                print(f'[INIT] Warning: Could not create cache table: {e}')


def load_fixtures():
    """Load Django fixtures if they exist."""
    from django.core.management import call_command
    import os
    
    fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures')
    
    # Only load states fixture (module backends require Excel files which aren't in git)
    fixture_files = ['states.json']
    
    for fixture_file in fixture_files:
        fixture_path = os.path.join(fixtures_dir, fixture_file)
        if os.path.exists(fixture_path):
            try:
                call_command('loaddata', fixture_path, verbosity=0)
                print(f'[INIT] Loaded fixture: {fixture_file}')
            except Exception as e:
                print(f'[INIT] Warning: Could not load {fixture_file}: {e}')


def seed_module_backends():
    """
    Seed ModuleBackend entries from static data files in core/data/.
    
    IMPORTANT: This only creates backends if NONE exist for a module+category.
    Once an admin has created/edited backends, they are never overwritten.
    This preserves admin customizations across deployments.
    """
    from subscriptions.models import ModuleBackend, Module
    from django.core.files import File
    
    # Map of static files to module backends
    # Format: (source_file, module_code, category, name, is_default)
    backend_configs = [
        ('electrical.xlsx', 'new_estimate', 'electrical', 'Telangana Electrical SOR 2024-25', True),
        ('civil.xlsx', 'new_estimate', 'civil', 'Telangana Civil SOR 2024-25', True),
        ('electrical.xlsx', 'workslip', 'electrical', 'Telangana Electrical SOR 2024-25', True),
        ('civil.xlsx', 'workslip', 'civil', 'Telangana Civil SOR 2024-25', True),
        ('temp_electrical.xlsx', 'temp_works', 'electrical', 'Telangana Temp Electrical SOR', True),
        ('temp_civil.xlsx', 'temp_works', 'civil', 'Telangana Temp Civil SOR', True),
        ('amc_electrical.xlsx', 'amc', 'electrical', 'AMC Electrical Rates', True),
        ('amc_civil.xlsx', 'amc', 'civil', 'AMC Civil Rates', True),
    ]
    
    static_data_dir = os.path.join(settings.BASE_DIR, 'core', 'data')
    media_backends_dir = os.path.join(settings.MEDIA_ROOT, 'module_backends')
    
    # Ensure media directory exists
    os.makedirs(media_backends_dir, exist_ok=True)
    
    backends_created = 0
    backends_skipped = 0
    backends_restored = 0
    
    for source_file, module_code, category, name, is_default in backend_configs:
        source_path = os.path.join(static_data_dir, source_file)
        
        if not os.path.exists(source_path):
            print(f'[INIT] Warning: Source file not found: {source_file}')
            continue
        
        # Get the module
        try:
            module = Module.objects.get(code=module_code)
        except Module.DoesNotExist:
            print(f'[INIT] Warning: Module not found: {module_code}')
            continue
        
        # Check if ANY backend exists for this module+category (active or inactive)
        # This ensures we NEVER overwrite admin changes
        existing = ModuleBackend.objects.filter(
            module=module,
            category=category
        ).first()
        
        if existing:
            # Backend exists - check if file needs restoration (for local storage only)
            # For S3/R2 storage, files persist automatically
            storage_backend = settings.STORAGES.get('default', {}).get('BACKEND', '')
            
            if 'S3Boto3Storage' in storage_backend:
                # Using cloud storage - files persist, skip entirely
                backends_skipped += 1
                continue
            
            # Using local storage - check if file exists
            if existing.file:
                try:
                    file_path = existing.file.path
                    if os.path.exists(file_path):
                        # File exists, don't touch it
                        backends_skipped += 1
                        continue
                    else:
                        # File is missing in local storage - restore it
                        print(f'[INIT] Restoring missing file for: {existing.name}')
                        dest_filename = f"{module_code}_{source_file}"
                        dest_path = os.path.join(media_backends_dir, dest_filename)
                        
                        try:
                            shutil.copy2(source_path, dest_path)
                            existing.file = f'module_backends/{dest_filename}'
                            existing.save(update_fields=['file'])  # Only update file, not other fields
                            backends_restored += 1
                            print(f'[INIT] Restored backend file: {existing.name}')
                        except Exception as e:
                            print(f'[INIT] Error restoring {source_file}: {e}')
                        continue
                except Exception:
                    # Can't determine file path, skip
                    backends_skipped += 1
                    continue
            else:
                # No file set but record exists - skip (admin may have intentionally cleared it)
                backends_skipped += 1
                continue
        
        # No backend exists at all - create initial one
        dest_filename = f"{module_code}_{source_file}"
        dest_path = os.path.join(media_backends_dir, dest_filename)
        
        try:
            shutil.copy2(source_path, dest_path)
        except Exception as e:
            print(f'[INIT] Error copying {source_file}: {e}')
            continue
        
        # Create new backend record
        ModuleBackend.objects.create(
            module=module,
            category=category,
            name=name,
            code=f'{module_code}_{category}_default',
            file=f'module_backends/{dest_filename}',
            is_active=True,
            is_default=is_default,
            display_order=0,
        )
        print(f'[INIT] Created initial backend: {name}')
        backends_created += 1
    
    if backends_created > 0:
        print(f'[INIT] Created {backends_created} initial module backends')
    if backends_restored > 0:
        print(f'[INIT] Restored {backends_restored} missing backend files')
    if backends_skipped > 0:
        print(f'[INIT] Preserved {backends_skipped} existing backends (no changes made)')


def check_storage_status():
    """Log the current storage configuration status."""
    from django.conf import settings
    
    storage_backend = settings.STORAGES.get('default', {}).get('BACKEND', 'unknown')
    
    if 'S3Boto3Storage' in storage_backend:
        bucket = settings.STORAGES.get('default', {}).get('OPTIONS', {}).get('bucket_name', 'unknown')
        print(f'[INIT] ✅ File storage: S3/R2 (bucket: {bucket})')
        print(f'[INIT] ✅ Uploaded files will persist across deploys')
    else:
        print(f'[INIT] ⚠️  File storage: Local filesystem')
        if os.environ.get('RAILWAY_ENVIRONMENT'):
            print(f'[INIT] ⚠️  WARNING: Files may be lost on Railway redeploy!')
            print(f'[INIT] ⚠️  Consider configuring S3/R2 storage for production')


def check_data_persistence():
    """
    Check and report on data persistence configuration.
    This helps identify issues before user data is lost.
    """
    from django.conf import settings
    from django.db import connection
    
    print('[INIT] ================================================')
    print('[INIT] DATA PERSISTENCE STATUS CHECK')
    print('[INIT] ================================================')
    
    is_production = os.environ.get('RAILWAY_ENVIRONMENT') or not settings.DEBUG
    all_ok = True
    
    # Check 1: Database type
    db_engine = settings.DATABASES.get('default', {}).get('ENGINE', '')
    if 'postgresql' in db_engine or 'postgres' in db_engine:
        print('[INIT] ✅ DATABASE: PostgreSQL (persistent)')
        
        # Count user data to show what's being preserved
        try:
            from django.contrib.auth.models import User
            from core.models import LetterSettings, SavedWork, SelfFormattedTemplate
            from subscriptions.models import ModuleBackend
            
            user_count = User.objects.count()
            letter_count = LetterSettings.objects.count()
            saved_work_count = SavedWork.objects.count()
            template_count = SelfFormattedTemplate.objects.count()
            backend_count = ModuleBackend.objects.count()
            
            print(f'[INIT]    • Users: {user_count}')
            print(f'[INIT]    • Letter Settings: {letter_count}')
            print(f'[INIT]    • Saved Works: {saved_work_count}')
            print(f'[INIT]    • Self-Formatted Templates: {template_count}')
            print(f'[INIT]    • Module Backends (SOR data): {backend_count}')
        except Exception as e:
            print(f'[INIT]    • Could not count records: {e}')
    else:
        print('[INIT] ❌ DATABASE: SQLite (EPHEMERAL - DATA WILL BE LOST!)')
        if is_production:
            print('[INIT]    ACTION REQUIRED: Add PostgreSQL to your Railway project')
            print('[INIT]    1. Go to Railway dashboard > Your project')
            print('[INIT]    2. Click "+ Add" > "PostgreSQL"')
            print('[INIT]    3. Redeploy - DATABASE_URL will be set automatically')
        all_ok = False
    
    # Check 2: File storage type
    storage_backend = settings.STORAGES.get('default', {}).get('BACKEND', '')
    if 'S3Boto3Storage' in storage_backend:
        bucket = settings.STORAGES.get('default', {}).get('OPTIONS', {}).get('bucket_name', 'unknown')
        print(f'[INIT] ✅ FILE STORAGE: S3/R2 (bucket: {bucket}) (persistent)')
    else:
        print('[INIT] ⚠️  FILE STORAGE: Local filesystem')
        if is_production:
            print('[INIT]    WARNING: Uploaded templates may be lost on redeploy!')
            print('[INIT]    RECOMMENDED: Configure S3 or Cloudflare R2 storage')
            print('[INIT]    Set these environment variables:')
            print('[INIT]      STORAGE_TYPE=s3 (or r2)')
            print('[INIT]      AWS_ACCESS_KEY_ID=your-key')
            print('[INIT]      AWS_SECRET_ACCESS_KEY=your-secret')
            print('[INIT]      AWS_STORAGE_BUCKET_NAME=your-bucket')
            all_ok = False
    
    # Summary
    print('[INIT] ------------------------------------------------')
    if all_ok:
        print('[INIT] ✅ All data persistence checks PASSED')
        print('[INIT] ✅ User data WILL persist across deployments')
    else:
        print('[INIT] ⚠️  Some data persistence issues detected')
        print('[INIT] ⚠️  Review the warnings above to prevent data loss')
    print('[INIT] ================================================')


if __name__ == '__main__':
    print('[INIT] Running startup initialization...')
    print('[INIT] ================================================')
    run_migrations()  # Run migrations first (must happen before other operations)
    setup_database_cache()  # Create cache table if needed
    create_admin()
    seed_modules()
    load_fixtures()
    seed_module_backends()  # Restore backends after each deploy
    check_data_persistence()  # Comprehensive data persistence check
    print('[INIT] ================================================')
    print('[INIT] Initialization complete!')
