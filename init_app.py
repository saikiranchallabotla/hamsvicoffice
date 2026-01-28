"""
Startup initialization script - runs on every app start.
Ensures admin user and modules are created.
"""
import os
import sys
import shutil
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'estimate_site.settings_railway')
django.setup()

from django.contrib.auth import get_user_model
from django.conf import settings
from accounts.models import UserProfile
from subscriptions.models import Module, ModulePricing

User = get_user_model()


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
    This restores backends after each Railway deploy when using ephemeral storage.
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
        
        # Check if backend already exists for this module+category
        existing = ModuleBackend.objects.filter(
            module=module,
            category=category,
            is_active=True
        ).first()
        
        if existing:
            # Check if the file exists in media
            if existing.file and os.path.exists(existing.file.path):
                backends_skipped += 1
                continue
            else:
                # File is missing - need to restore it
                print(f'[INIT] Restoring missing file for: {name}')
        
        # Copy file to media directory
        dest_filename = f"{module_code}_{source_file}"
        dest_path = os.path.join(media_backends_dir, dest_filename)
        
        try:
            shutil.copy2(source_path, dest_path)
        except Exception as e:
            print(f'[INIT] Error copying {source_file}: {e}')
            continue
        
        # Create or update ModuleBackend entry
        if existing:
            # Update existing record with new file path
            existing.file = f'module_backends/{dest_filename}'
            existing.save()
            print(f'[INIT] Restored backend file: {name}')
        else:
            # Create new record
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
            print(f'[INIT] Created backend: {name}')
        
        backends_created += 1
    
    if backends_created > 0:
        print(f'[INIT] Seeded {backends_created} module backends from static files')
    if backends_skipped > 0:
        print(f'[INIT] Skipped {backends_skipped} backends (already exist)')


if __name__ == '__main__':
    print('[INIT] Running startup initialization...')
    create_admin()
    seed_modules()
    load_fixtures()
    seed_module_backends()  # Restore backends after each deploy
    print('[INIT] Initialization complete!')
