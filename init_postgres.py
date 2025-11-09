#!/usr/bin/env python3
"""
Initialize PostgreSQL database schema
Creates all tables defined in SQLAlchemy models
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from models.database import init_db, engine

async def main():
    print("🐘 Initializing PostgreSQL Database Schema...")
    print(f"   Database: {engine.url}")
    print()
    
    try:
        await init_db()
        print("✅ Database schema created successfully!")
        print()
        print("📊 Tables created:")
        print("   • watchlist")
        print("   • signals")
        print("   • risk_events")
        print("   • pnl_reports")
        print("   • settings")
        print()
        return True
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
