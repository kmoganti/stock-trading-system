"""
Database migration script to add missing columns for compatibility.
"""
import sqlite3
import os

def migrate_database():
    """Add missing columns to existing database tables"""
    db_path = "trading_system.db"
    
    if not os.path.exists(db_path):
        print("No existing database found - new database will be created with all columns")
        return
    
    print("Migrating existing database...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if fees column exists in pnl_reports
        cursor.execute("PRAGMA table_info(pnl_reports);")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'fees' not in columns:
            print("Adding 'fees' column to pnl_reports table...")
            cursor.execute("ALTER TABLE pnl_reports ADD COLUMN fees FLOAT DEFAULT 0.0;")
            print("✅ Added 'fees' column successfully")
        else:
            print("✅ 'fees' column already exists")
        
        # Check other potential missing columns
        migrations_applied = []
        
        # Check if category column exists in watchlist (should already be there from init_db)
        cursor.execute("PRAGMA table_info(watchlist);")  
        watchlist_columns = [col[1] for col in cursor.fetchall()]
        
        if 'category' not in watchlist_columns:
            print("Adding 'category' column to watchlist table...")
            cursor.execute("ALTER TABLE watchlist ADD COLUMN category VARCHAR(20) NOT NULL DEFAULT 'short_term';")
            migrations_applied.append("watchlist.category")
        
        if 'is_active' not in watchlist_columns:
            print("Adding 'is_active' column to watchlist table...")
            cursor.execute("ALTER TABLE watchlist ADD COLUMN is_active BOOLEAN DEFAULT 1;")
            migrations_applied.append("watchlist.is_active")
        
        conn.commit()
        
        if migrations_applied:
            print(f"✅ Applied migrations: {', '.join(migrations_applied)}")
        else:
            print("✅ Database schema is up to date")
            
    except Exception as e:
        print(f"❌ Migration error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()