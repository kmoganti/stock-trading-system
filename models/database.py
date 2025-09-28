from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import MetaData, text
import logging
import sqlite3
from sqlalchemy import inspect
import os
from typing import AsyncGenerator

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./trading_system.db")

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Create base class for models
Base = declarative_base()


async def ensure_pnl_columns(engine):
    """Ensure compatibility columns exist in pnl_reports table for older DB files.

    This is a small, safe helper: it only runs ALTER TABLE ADD COLUMN for columns
    that don't already exist. It's idempotent and intended for local/dev SQLite
    files used in tests.
    """
    inspector = inspect(engine)
    try:
        cols = {c['name'] for c in inspector.get_columns('pnl_reports')}
    except Exception:
        # Table probably doesn't exist yet; nothing to do here.
        logging.getLogger(__name__).debug("pnl_reports table not present yet")
        return

    needed = {
        'total_pnl': 'REAL',
        'fees': 'REAL',
        'trades_count': 'INTEGER',
        'win_rate': 'REAL',
    }

    conn = engine.raw_connection()
    try:
        cur = conn.cursor()
        for name, col_type in needed.items():
            if name not in cols:
                logging.getLogger(__name__).info(f"Adding missing column {name} to pnl_reports")
                # ALTER TABLE ADD COLUMN is supported by SQLite for simple types
                cur.execute(f"ALTER TABLE pnl_reports ADD COLUMN {name} {col_type} DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        # In case the DB is locked or another error occurs, log and continue.
        logging.getLogger(__name__).exception("Error while ensuring pnl columns")
    finally:
        conn.close()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # SQLite compatibility: ensure new columns exist on older databases
        try:
            if engine.url.get_backend_name().startswith("sqlite"):
                # Inspect existing columns
                result = await conn.execute(text("PRAGMA table_info('watchlist')"))
                columns = {row[1] for row in result.fetchall()}  # row[1] is column name
                if "category" not in columns:
                    await conn.execute(text("ALTER TABLE watchlist ADD COLUMN category VARCHAR(20) NOT NULL DEFAULT 'short_term'"))
                if "is_active" not in columns:
                    await conn.execute(text("ALTER TABLE watchlist ADD COLUMN is_active BOOLEAN DEFAULT 1"))
        except Exception:
            # Best-effort; do not block startup if pragma/alter fails
            pass

async def close_db():
    """Close database connections"""
    await engine.dispose()
