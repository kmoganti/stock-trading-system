import sqlite3, json
fn = r"trading_system.db"
conn = sqlite3.connect(fn)
cur = conn.cursor()
cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
rows = cur.fetchall()
schema = {name: sql for name, sql in rows}
print(json.dumps(schema, indent=2))
conn.close()
