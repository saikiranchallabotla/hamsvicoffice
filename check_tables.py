import sqlite3
conn = sqlite3.connect('db.sqlite3')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = c.fetchall()
backend_tables = [t[0] for t in tables if 'backend' in t[0].lower()]
print('Backend tables:', backend_tables)
print('All subscriptions tables:', [t[0] for t in tables if 'subscription' in t[0].lower()])
conn.close()
