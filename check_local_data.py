"""
Check what data exists in the local SQLite database.
"""
import sqlite3
import os

os.chdir(r"e:\Version 3\Windows x 1")
conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("=" * 60)
print("LOCAL SQLITE DATABASE DATA SUMMARY")
print("=" * 60)

for t in sorted(tables):
    table_name = t[0]
    if table_name.startswith('sqlite_'):
        continue
    try:
        cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
        count = cursor.fetchone()[0]
        if count > 0:
            print(f"  {table_name}: {count} rows")
    except Exception as e:
        print(f"  {table_name}: ERROR - {e}")

# Check for backend tables specifically
print("\n" + "=" * 60)
print("BACKEND WORKBOOK TABLES")
print("=" * 60)
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%backend%'")
backend_tables = cursor.fetchall()
for t in backend_tables:
    print(f"  Found: {t[0]}")
    cursor.execute(f"SELECT COUNT(*) FROM [{t[0]}]")
    print(f"    Rows: {cursor.fetchone()[0]}")

# Check media folder for Excel files
print("\n" + "=" * 60)
print("MEDIA FILES (backend_excels)")
print("=" * 60)
excel_path = r"e:\Version 3\Windows x 1\media\backend_excels"
if os.path.exists(excel_path):
    files = os.listdir(excel_path)
    print(f"  Found {len(files)} files:")
    for f in files:
        print(f"    - {f}")
else:
    print("  No backend_excels folder found")

conn.close()
print("=" * 60)
