#!/usr/bin/env python
"""
One-time script to fix the Temporary Works module code in the database.
Changes 'tempworks' to 'temp_works' to match the seed data.

Run with: python manage.py shell < fix_tempworks_module.py
Or run directly: python fix_tempworks_module.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'estimate_site.settings')

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

from subscriptions.models import Module

def fix_tempworks_module():
    """Fix the Temporary Works module code from 'tempworks' to 'temp_works'."""
    
    # Check if module with 'tempworks' code exists
    try:
        module = Module.objects.get(code='tempworks')
        old_code = module.code
        module.code = 'temp_works'
        module.save()
        print(f"✓ Updated module code from '{old_code}' to 'temp_works'")
        print(f"  Module: {module.name} (ID: {module.pk})")
        return True
    except Module.DoesNotExist:
        # Check if temp_works already exists
        try:
            module = Module.objects.get(code='temp_works')
            print(f"✓ Module 'temp_works' already exists (ID: {module.pk})")
            return True
        except Module.DoesNotExist:
            print("✗ Neither 'tempworks' nor 'temp_works' module found!")
            print("  You may need to run: python manage.py seed_modules")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == '__main__':
    print("=" * 50)
    print("Fixing Temporary Works Module Code")
    print("=" * 50)
    success = fix_tempworks_module()
    print("=" * 50)
    if success:
        print("Done! The Backend Data Management page should now show Temporary Works.")
    else:
        print("Please check the error above and try again.")
