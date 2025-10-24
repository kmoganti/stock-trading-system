"""
Fast database initialization script
Optimizes database startup performance by skipping unnecessary checks.
"""

import asyncio
import logging
import sqlite3
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fast_db_init():
    """Fast database initialization without heavy checks"""
    
    db_file = Path("trading_system.db")
    
    # If database exists and is not empty, skip heavy initialization
    if db_file.exists() and db_file.stat().st_size > 1000:
        logger.info("✅ Database exists and appears populated, skipping heavy init")
        return
    
    logger.info("🔧 Running fast database initialization...")
    
    # Create async engine with minimal settings
    engine = create_async_engine(
        "sqlite+aiosqlite:///./trading_system.db",
        echo=False,
        pool_pre_ping=False,  # Disable ping for faster startup
        future=True
    )
    
    try:
        async with engine.begin() as conn:
            # Just ensure basic tables exist without column checks
            from models.database import Base
            await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables created/verified")
            
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {str(e)}")
        raise
    finally:
        await engine.dispose()

async def check_db_performance():
    """Check database performance"""
    import time
    
    logger.info("🔍 Testing database performance...")
    
    start_time = time.perf_counter()
    
    # Test basic connection
    engine = create_async_engine(
        "sqlite+aiosqlite:///./trading_system.db",
        echo=False,
        pool_pre_ping=False
    )
    
    async with engine.begin() as conn:
        # Simple query
        result = await conn.execute(text("SELECT 1"))
        result.fetchone()
    
    await engine.dispose()
    
    duration = time.perf_counter() - start_time
    logger.info(f"⏱️ Database connection test: {duration:.3f}s")
    
    if duration > 1.0:
        logger.warning("⚠️ Slow database performance detected")
    else:
        logger.info("✅ Database performance is good")

def sync_check_db_structure():
    """Synchronously check database structure using sqlite3"""
    try:
        conn = sqlite3.connect("trading_system.db")
        cursor = conn.cursor()
        
        # Check if watchlist table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='watchlist'")
        has_watchlist = cursor.fetchone() is not None
        
        if has_watchlist:
            # Check columns
            cursor.execute("PRAGMA table_info(watchlist)")
            columns = {row[1] for row in cursor.fetchall()}
            
            logger.info(f"📊 Watchlist table columns: {columns}")
            
            missing_columns = []
            if "category" not in columns:
                missing_columns.append("category")
            if "is_active" not in columns:
                missing_columns.append("is_active")
                
            if missing_columns:
                logger.warning(f"⚠️ Missing columns: {missing_columns}")
            else:
                logger.info("✅ All required columns present")
        else:
            logger.info("ℹ️ Watchlist table does not exist yet")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Sync database check failed: {str(e)}")

async def main():
    """Main function"""
    logger.info("🚀 Fast Database Diagnostics & Optimization")
    logger.info("=" * 50)
    
    # Sync check first (faster)
    sync_check_db_structure()
    
    # Performance test
    await check_db_performance()
    
    # Fast initialization
    await fast_db_init()
    
    logger.info("✅ Database diagnostics completed")

if __name__ == "__main__":
    asyncio.run(main())