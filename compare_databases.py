"""Compare data between SQLite and PostgreSQL databases"""
import os
import sqlite3

# Check SQLite
print("=" * 60)
print("SQLITE DATABASE (Local)")
print("=" * 60)

conn = sqlite3.connect('db.sqlite3')
c = conn.cursor()

tables = [
    'datasets_state', 
    'subscriptions_module', 
    'subscriptions_modulebackend', 
    'subscriptions_modulepricing', 
    'core_organization', 
    'core_job', 
    'auth_user'
]

sqlite_counts = {}
for table in tables:
    try:
        c.execute(f'SELECT COUNT(*) FROM {table}')
        count = c.fetchone()[0]
        sqlite_counts[table] = count
        print(f"  {table}: {count}")
    except Exception as e:
        print(f"  {table}: ERROR - {e}")
        sqlite_counts[table] = 0

conn.close()

# Check PostgreSQL
print("\n" + "=" * 60)
print("POSTGRESQL DATABASE (Neon Cloud)")
print("=" * 60)

os.environ['DJANGO_SETTINGS_MODULE'] = 'estimate_site.settings'
os.environ['DB_ENGINE'] = 'postgresql'

import django
django.setup()

from django.db import connection

pg_counts = {}
with connection.cursor() as cursor:
    for table in tables:
        try:
            cursor.execute(f'SELECT COUNT(*) FROM {table}')
            count = cursor.fetchone()[0]
            pg_counts[table] = count
            print(f"  {table}: {count}")
        except Exception as e:
            print(f"  {table}: ERROR - {e}")
            pg_counts[table] = 0

# Compare
print("\n" + "=" * 60)
print("COMPARISON")
print("=" * 60)
print(f"{'Table':<35} {'SQLite':<10} {'PostgreSQL':<10} {'Status'}")
print("-" * 60)

all_match = True
for table in tables:
    sq = sqlite_counts.get(table, 0)
    pg = pg_counts.get(table, 0)
    if sq == pg:
        status = "✓ Match"
    elif sq > pg:
        status = f"⚠ SQLite has {sq - pg} more"
        all_match = False
    else:
        status = f"⚠ PostgreSQL has {pg - sq} more"
        all_match = False
    print(f"{table:<35} {sq:<10} {pg:<10} {status}")

print("-" * 60)
if all_match:
    print("✅ All data is synchronized!")
else:
    print("⚠️  Data mismatch detected - sync needed")
