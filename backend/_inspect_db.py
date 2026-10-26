import sqlite3

c = sqlite3.connect(r"sql_app.db")
print("TABLES")
for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
    print(r)
print("--- ITEMS COLS ---")
for r in c.execute("PRAGMA table_info(items)"):
    print(r)
print("--- ITEMS ---")
for r in c.execute("SELECT * FROM items"):
    print(r)
print("--- PURCHASES COLS ---")
try:
    for r in c.execute("PRAGMA table_info(purchases)"):
        print(r)
    print("--- PURCHASES ---")
    for r in c.execute("SELECT * FROM purchases"):
        print(r)
except Exception as e:
    print(type(e), e)
print("--- STOCK ---")
try:
    for r in c.execute("SELECT * FROM stock_movements"):
        print(r)
except Exception as e:
    print(type(e), e)
print("--- USERS ---")
for r in c.execute("SELECT * FROM users"):
    print(r)
