import sqlite3
import os

# Check existing database schema
db_path = "trading_system.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    print("Existing tables:", tables)
    
    # Check schema for each table
    for table in tables:
        print(f"\n--- Schema for {table} ---")
        cursor.execute(f"PRAGMA table_info({table});")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  {col[1]} {col[2]} {'NOT NULL' if col[3] else ''}")
    
    conn.close()
else:
    print("No database found")