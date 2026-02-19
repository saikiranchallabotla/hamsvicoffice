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
    NON-DESTRUCTIVE backend persistence during deployment.

    This function guarantees:
    - No automatic renaming of backend files
    - No automatic rewriting of existing backend file contents
    - Admin-modified files survive all redeployments
    - Overwrites ONLY with hash mismatch detection + backup
    - admin_locked backends are NEVER touched by automation

    Flow:
    1. Pre-deployment validation (integrity check all backends)
    2. Conflict detection (disk vs DB hash comparison)
    3. Backup creation (before any file write)
    4. Safe restoration (only missing disk files from authoritative DB)
    5. Optional initial seeding (only when SEED_INITIAL_BACKENDS=true)
    """
    from subscriptions.models import ModuleBackend, Module
    from core.deployment_safety import (
        log_deployment_event,
        run_pre_deployment_checks,
        compute_file_hash,
    )

    print('[INIT] ---- Backend Persistence Engine (Non-Destructive) ----')

    # Phase 1: Pre-deployment validation
    log_deployment_event('START', 'Beginning backend persistence check')
    all_ok, report = run_pre_deployment_checks()
    print(f'[INIT] Pre-check: {report["total_backends"]} backends '
          f'({report["healthy"]} healthy, {report["disk_missing"]} disk-missing, '
          f'{report["conflicts"]} conflicts, {report["admin_locked"]} admin-locked)')

    # Phase 2: Backfill hashes for any backends missing them
    _backfill_missing_hashes()

    # Phase 3: Non-destructive file restoration
    restore_missing_backend_files()

    # Phase 4: Optional initial seeding (only when explicitly requested)
    seed_initial = os.environ.get('SEED_INITIAL_BACKENDS', 'false').lower() == 'true'
    if seed_initial:
        _seed_initial_backends()

    log_deployment_event('COMPLETE', 'Backend persistence check finished')
    print('[INIT] ---- Backend Persistence Engine Complete ----')


def _backfill_missing_hashes():
    """Backfill file_hash for any backends that have file_data but no hash."""
    from subscriptions.models import ModuleBackend
    from core.deployment_safety import compute_file_hash

    updated = 0
    for backend in ModuleBackend.objects.filter(file_data__isnull=False).exclude(file_data=b''):
        if not backend.file_hash and backend.file_data:
            file_hash = compute_file_hash(bytes(backend.file_data))
            ModuleBackend.objects.filter(pk=backend.pk).update(file_hash=file_hash)
            updated += 1

    if updated > 0:
        print(f'[INIT] Backfilled file hashes for {updated} backends')


def _seed_initial_backends():
    """
    Create initial backend records ONLY when no backends exist for a module+category.
    This is a one-time setup operation triggered by SEED_INITIAL_BACKENDS=true.

    Safety: Uses exists() check - never overwrites existing records.
    """
    from subscriptions.models import ModuleBackend, Module
    from core.deployment_safety import compute_file_hash, log_deployment_event

    print('[INIT] SEED_INITIAL_BACKENDS=true - Creating initial backends...')

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
    os.makedirs(media_backends_dir, exist_ok=True)

    backends_created = 0

    for source_file, module_code, category, name, is_default in backend_configs:
        source_path = os.path.join(static_data_dir, source_file)

        if not os.path.exists(source_path):
            continue

        try:
            module = Module.objects.get(code=module_code)
        except Module.DoesNotExist:
            continue

        # SAFETY: Skip if ANY backend exists for this module+category
        if ModuleBackend.objects.filter(module=module, category=category).exists():
            log_deployment_event(
                'SKIP_SEED',
                f'Backend already exists for {module_code}/{category}, skipping seed',
            )
            continue

        # Copy file and create backend with full metadata
        dest_filename = f"{module_code}_{source_file}"
        dest_path = os.path.join(media_backends_dir, dest_filename)

        try:
            shutil.copy2(source_path, dest_path)
            with open(dest_path, 'rb') as f:
                file_data = f.read()
            file_hash = compute_file_hash(file_data)

            ModuleBackend.objects.create(
                module=module,
                category=category,
                name=name,
                code=f'{module_code}_{category}_default',
                file=f'module_backends/{dest_filename}',
                file_data=file_data,
                file_name=dest_filename,
                file_hash=file_hash,
                version=1,
                source_type='seed',
                admin_locked=False,
                is_active=True,
                is_default=is_default,
                display_order=0,
            )
            backends_created += 1
            log_deployment_event('SEED', f'Created initial backend: {name}')
        except Exception as e:
            print(f'[INIT] Error creating backend {name}: {e}')

    if backends_created > 0:
        print(f'[INIT] Created {backends_created} initial backends')

    print('[INIT] TIP: Remove SEED_INITIAL_BACKENDS env var after first deploy')


def restore_missing_backend_files():
    """
    NON-DESTRUCTIVE restoration of missing backend disk files.

    This function ONLY restores files that are missing from disk.
    It NEVER overwrites existing files. It NEVER renames files.

    Safety guarantees:
    1. admin_locked backends are NEVER modified by automation
    2. Existing disk files are NEVER overwritten (hash comparison first)
    3. DB file_data is ALWAYS authoritative - static fallback is last resort
    4. Backups are created before any write operation
    5. Original filenames are preserved (no renaming)
    6. Every operation is logged with before/after hash
    7. file_hash is computed and stored on every restoration
    8. Backends with source_type='admin' get extra protection

    Only needed for local storage - cloud storage files persist automatically.
    """
    from subscriptions.models import ModuleBackend
    from core.deployment_safety import (
        compute_file_hash,
        compute_file_hash_from_path,
        safe_write_backend_file,
        create_backup,
        log_deployment_event,
    )

    # Skip if using cloud storage (files persist automatically)
    storage_backend = settings.STORAGES.get('default', {}).get('BACKEND', '')
    if 'S3Boto3Storage' in storage_backend:
        log_deployment_event('SKIP', 'Cloud storage detected, skipping disk restoration')
        return

    static_data_dir = os.path.join(settings.BASE_DIR, 'core', 'data')
    media_backends_dir = os.path.join(settings.MEDIA_ROOT, 'module_backends')

    # Static file mapping (ONLY used as absolute last resort for seed-type backends)
    file_mapping = {
        'new_estimate_electrical': 'electrical.xlsx',
        'new_estimate_civil': 'civil.xlsx',
        'workslip_electrical': 'electrical.xlsx',
        'workslip_civil': 'civil.xlsx',
        'temp_works_electrical': 'temp_electrical.xlsx',
        'temp_works_civil': 'temp_civil.xlsx',
        'amc_electrical': 'amc_electrical.xlsx',
        'amc_civil': 'amc_civil.xlsx',
    }

    stats = {
        'skipped_locked': 0,
        'skipped_identical': 0,
        'restored_from_db': 0,
        'restored_from_static': 0,
        'backfilled_to_db': 0,
        'errors': 0,
    }

    from django.utils import timezone as tz

    for backend in ModuleBackend.objects.filter(file__isnull=False).exclude(file=''):
        if not backend.file:
            continue

        # ---- SAFETY: Never touch admin-locked backends ----
        if getattr(backend, 'admin_locked', False):
            stats['skipped_locked'] += 1
            log_deployment_event('SKIP_LOCKED', f'Admin-locked, not touching', backend=backend)
            continue

        # Check disk file status
        try:
            file_path = backend.file.path
            file_exists = os.path.exists(file_path)
        except Exception:
            file_exists = False
            file_path = None

        # ================================================================
        # CASE 1: File EXISTS on disk
        # ================================================================
        if file_exists:
            # Backfill to DB if not already stored (non-destructive)
            if not backend.file_data:
                try:
                    with open(file_path, 'rb') as f:
                        data = f.read()
                    file_hash = compute_file_hash(data)
                    ModuleBackend.objects.filter(pk=backend.pk).update(
                        file_data=data,
                        file_name=os.path.basename(file_path),
                        file_hash=file_hash,
                        last_verified_at=tz.now(),
                    )
                    stats['backfilled_to_db'] += 1
                    log_deployment_event(
                        'BACKFILL',
                        f'Backfilled disk->DB (hash={file_hash[:12]}...)',
                        backend=backend,
                    )
                except Exception as e:
                    stats['errors'] += 1
                    log_deployment_event('ERROR', f'Backfill failed: {e}', backend=backend)
            else:
                # Both exist - verify integrity only, no writes
                disk_hash = compute_file_hash_from_path(file_path)
                db_hash = compute_file_hash(bytes(backend.file_data))

                if disk_hash == db_hash:
                    # Consistent - just update verification timestamp
                    update_fields = {'last_verified_at': tz.now()}
                    if not backend.file_hash:
                        update_fields['file_hash'] = db_hash
                    ModuleBackend.objects.filter(pk=backend.pk).update(**update_fields)
                else:
                    # CONFLICT: Disk differs from DB
                    # DB is authoritative for admin uploads, but we log and do NOT overwrite disk
                    # The admin's disk modifications should be preserved
                    log_deployment_event(
                        'CONFLICT',
                        f'Disk hash ({disk_hash[:12]}) differs from DB ({db_hash[:12]}). '
                        f'NOT overwriting - admin modifications preserved on disk.',
                        backend=backend,
                    )
                    # If source is admin, trust disk and update DB from disk
                    source = getattr(backend, 'source_type', '') or 'admin'
                    if source == 'admin':
                        try:
                            with open(file_path, 'rb') as f:
                                disk_data = f.read()
                            ModuleBackend.objects.filter(pk=backend.pk).update(
                                file_data=disk_data,
                                file_hash=disk_hash,
                                last_verified_at=tz.now(),
                            )
                            log_deployment_event(
                                'SYNC_DISK_TO_DB',
                                f'Admin backend: synced disk->DB (hash={disk_hash[:12]}...)',
                                backend=backend,
                            )
                        except Exception as e:
                            log_deployment_event(
                                'ERROR',
                                f'Disk->DB sync failed: {e}',
                                backend=backend,
                            )
            continue

        # ================================================================
        # CASE 2: File MISSING on disk - restore from DB (authoritative)
        # ================================================================
        if backend.file_data:
            try:
                os.makedirs(media_backends_dir, exist_ok=True)

                # PRESERVE original filename - never rename
                restore_name = backend.file_name or os.path.basename(backend.file.name)
                dest_path = os.path.join(media_backends_dir, restore_name)

                data = bytes(backend.file_data)
                file_hash = compute_file_hash(data)

                success, action, details = safe_write_backend_file(
                    backend, data, dest_path, reason='db_restore'
                )

                if success:
                    # Update file field to point to restored file
                    # Use queryset.update() to avoid changing updated_at
                    ModuleBackend.objects.filter(pk=backend.pk).update(
                        file=f'module_backends/{restore_name}',
                        file_hash=file_hash,
                        last_verified_at=tz.now(),
                    )
                    stats['restored_from_db'] += 1
                    log_deployment_event(
                        'RESTORE_DB',
                        f'Restored from DB (hash={file_hash[:12]}..., name={restore_name})',
                        backend=backend,
                    )
                else:
                    stats['errors'] += 1

                continue

            except Exception as e:
                stats['errors'] += 1
                log_deployment_event('ERROR', f'DB restore failed: {e}', backend=backend)

        # ================================================================
        # CASE 3: LAST RESORT - static data (ONLY for seed-type backends)
        # ================================================================
        # SAFETY: Only use static fallback for backends that were originally seeded,
        # NEVER for admin-uploaded backends. Admin backends without DB data are logged
        # as errors but NOT overwritten with generic templates.
        source = getattr(backend, 'source_type', '') or ''
        if source == 'admin':
            log_deployment_event(
                'WARN',
                f'Admin backend has no DB data and no disk file. '
                f'Cannot restore - requires manual admin re-upload.',
                backend=backend,
            )
            stats['errors'] += 1
            continue

        key = f"{backend.module.code}_{backend.category}"
        source_file = file_mapping.get(key)

        if not source_file:
            log_deployment_event(
                'WARN',
                f'No static fallback available for {key}',
                backend=backend,
            )
            continue

        source_path = os.path.join(static_data_dir, source_file)
        if not os.path.exists(source_path):
            continue

        os.makedirs(media_backends_dir, exist_ok=True)

        # PRESERVE the backend's existing filename pattern, don't rename
        existing_name = backend.file_name or os.path.basename(backend.file.name)
        if not existing_name or existing_name == '':
            existing_name = f"{backend.module.code}_{source_file}"
        dest_path = os.path.join(media_backends_dir, existing_name)

        try:
            with open(source_path, 'rb') as f:
                data = f.read()
            file_hash = compute_file_hash(data)

            success, action, details = safe_write_backend_file(
                backend, data, dest_path, reason='static_fallback'
            )

            if success:
                ModuleBackend.objects.filter(pk=backend.pk).update(
                    file=f'module_backends/{existing_name}',
                    file_data=data,
                    file_name=existing_name,
                    file_hash=file_hash,
                    source_type='static',
                    last_verified_at=tz.now(),
                )
                stats['restored_from_static'] += 1
                log_deployment_event(
                    'RESTORE_STATIC',
                    f'Restored from static (hash={file_hash[:12]}..., name={existing_name})',
                    backend=backend,
                )
            else:
                stats['errors'] += 1

        except Exception as e:
            stats['errors'] += 1
            log_deployment_event('ERROR', f'Static restore failed: {e}', backend=backend)

    # Print summary
    print(f'[INIT] Backend restoration summary:')
    if stats['restored_from_db'] > 0:
        print(f'[INIT]   Restored from DB: {stats["restored_from_db"]}')
    if stats['restored_from_static'] > 0:
        print(f'[INIT]   Restored from static: {stats["restored_from_static"]}')
    if stats['backfilled_to_db'] > 0:
        print(f'[INIT]   Backfilled to DB: {stats["backfilled_to_db"]}')
    if stats['skipped_locked'] > 0:
        print(f'[INIT]   Skipped (admin-locked): {stats["skipped_locked"]}')
    if stats['skipped_identical'] > 0:
        print(f'[INIT]   Skipped (identical): {stats["skipped_identical"]}')
    if stats['errors'] > 0:
        print(f'[INIT]   Errors: {stats["errors"]}')


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
    seed_module_backends()  # Non-destructive backend persistence
    check_data_persistence()  # Comprehensive data persistence check
    print('[INIT] ================================================')
    print('[INIT] Initialization complete!')
