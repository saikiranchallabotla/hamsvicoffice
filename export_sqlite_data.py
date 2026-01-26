"""
SQLite to PostgreSQL Migration Script
=====================================
This script exports all data from SQLite and imports it into PostgreSQL.
"""

import os
import sys
import json
import django
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'estimate_site.settings')

# Temporarily force SQLite for export
os.environ['DB_ENGINE'] = 'sqlite3'

# Setup Django
sys.path.insert(0, str(Path(__file__).parent))
django.setup()

from django.core.management import call_command
from django.conf import settings

def export_sqlite_data():
    """Export all data from SQLite database to JSON."""
    print("=" * 60)
    print("STEP 1: Exporting data from SQLite...")
    print("=" * 60)
    
    output_file = 'sqlite_data_backup.json'
    
    # Use dumpdata to export all data
    with open(output_file, 'w', encoding='utf-8') as f:
        call_command(
            'dumpdata',
            '--natural-foreign',
            '--natural-primary',
            '--exclude=contenttypes',
            '--exclude=auth.Permission',
            '--exclude=admin.logentry',
            '--exclude=sessions.session',
            '--indent=2',
            stdout=f
        )
    
    print(f"✅ Data exported to {output_file}")
    
    # Get file size
    size = os.path.getsize(output_file)
    print(f"   File size: {size / 1024:.2f} KB")
    
    return output_file

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("SQLite DATA EXPORT")
    print("=" * 60 + "\n")
    
    try:
        backup_file = export_sqlite_data()
        print("\n" + "=" * 60)
        print("EXPORT COMPLETE!")
        print("=" * 60)
        print(f"\nBackup saved to: {backup_file}")
        print("\nNext step: Run 'python migrate_to_postgres.py' to import to PostgreSQL")
    except Exception as e:
        print(f"\n❌ Error during export: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
