"""
Direct Data Transfer from SQLite to PostgreSQL
==============================================
This script directly reads from SQLite and writes to PostgreSQL
without using Django's dumpdata/loaddata commands.
"""

import os
import sys
import sqlite3
import json
from pathlib import Path

# PostgreSQL connection
import psycopg2
from psycopg2.extras import execute_values

# Load environment
from dotenv import load_dotenv
load_dotenv()

# Database paths
SQLITE_PATH = Path(__file__).parent / 'db.sqlite3'

# PostgreSQL connection details
PG_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'neondb'),
    'user': os.getenv('DB_USER', 'neondb_owner'),
    'password': os.getenv('DB_PASSWORD', ''),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'sslmode': 'require'
}

def get_sqlite_tables(cursor):
    """Get all table names from SQLite"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    return [row[0] for row in cursor.fetchall()]

def get_table_data(cursor, table):
    """Get all data from a SQLite table"""
    cursor.execute(f"SELECT * FROM {table}")
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    return columns, rows

def transfer_table(sqlite_cursor, pg_cursor, table, skip_tables=None):
    """Transfer a single table from SQLite to PostgreSQL"""
    if skip_tables and table in skip_tables:
        print(f"   ⏭ {table}: Skipped")
        return 0
    
    try:
        columns, rows = get_table_data(sqlite_cursor, table)
        
        if not rows:
            print(f"   ○ {table}: Empty")
            return 0
        
        # Check if table exists in PostgreSQL
        pg_cursor.execute(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = %s
            );
        """, (table,))
        
        if not pg_cursor.fetchone()[0]:
            print(f"   ⚠ {table}: Table doesn't exist in PostgreSQL")
            return 0
        
        # Clear existing data (be careful with foreign keys)
        try:
            pg_cursor.execute(f"DELETE FROM {table}")
        except Exception as e:
            print(f"   ⚠ {table}: Cannot delete - {e}")
        
        # Build insert query
        cols_str = ', '.join(f'"{c}"' for c in columns)
        placeholders = ', '.join(['%s'] * len(columns))
        
        # Insert data
        insert_sql = f'INSERT INTO {table} ({cols_str}) VALUES ({placeholders})'
        
        inserted = 0
        for row in rows:
            try:
                pg_cursor.execute(insert_sql, row)
                inserted += 1
            except Exception as e:
                # Try without the id column for auto-increment
                if 'id' in columns:
                    try:
                        idx = columns.index('id')
                        new_cols = [c for i, c in enumerate(columns) if i != idx]
                        new_row = tuple(v for i, v in enumerate(row) if i != idx)
                        cols_str2 = ', '.join(f'"{c}"' for c in new_cols)
                        placeholders2 = ', '.join(['%s'] * len(new_cols))
                        pg_cursor.execute(f'INSERT INTO {table} ({cols_str2}) VALUES ({placeholders2})', new_row)
                        inserted += 1
                    except:
                        pass
        
        print(f"   ✓ {table}: {inserted}/{len(rows)} records")
        return inserted
        
    except Exception as e:
        print(f"   ✗ {table}: Error - {str(e)[:50]}")
        return 0

def main():
    print("=" * 70)
    print("DIRECT DATA TRANSFER: SQLite → PostgreSQL")
    print("=" * 70)
    
    # Connect to SQLite
    print("\n[1/3] Connecting to SQLite...")
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_cursor = sqlite_conn.cursor()
    
    # Connect to PostgreSQL
    print("[2/3] Connecting to PostgreSQL (Neon)...")
    try:
        pg_conn = psycopg2.connect(**PG_CONFIG)
        pg_conn.autocommit = True  # Each statement commits immediately
        pg_cursor = pg_conn.cursor()
        print("   ✓ Connected to PostgreSQL")
    except Exception as e:
        print(f"   ✗ Failed to connect: {e}")
        return
    
    # Get all tables
    tables = get_sqlite_tables(sqlite_cursor)
    print(f"\n[3/3] Transferring {len(tables)} tables...")
    
    # Tables to skip (Django will recreate these)
    skip_tables = {
        'django_migrations',
        'django_content_type',
        'auth_permission',
        'django_admin_log',
        'django_session',
        'sqlite_sequence',
    }
    
    # Priority order for tables (foreign key dependencies)
    priority_tables = [
        'auth_user',
        'datasets_state',
        'subscriptions_module',
        'subscriptions_modulebackend',
        'core_organization',
        'core_membership',
        'accounts_userprofile',
        'subscriptions_modulepricing',
    ]
    
    # Transfer priority tables first
    transferred = 0
    for table in priority_tables:
        if table in tables:
            transferred += transfer_table(sqlite_cursor, pg_cursor, table, skip_tables)
    
    # Transfer remaining tables
    for table in tables:
        if table not in priority_tables:
            transferred += transfer_table(sqlite_cursor, pg_cursor, table, skip_tables)
    
    # Close connections
    sqlite_conn.close()
    pg_conn.close()
    
    print("\n" + "=" * 70)
    print(f"TRANSFER COMPLETE! {transferred} total records transferred")
    print("=" * 70)

if __name__ == '__main__':
    main()
