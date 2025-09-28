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


async def ensure_pnl_columns(async_engine):
    """Ensure compatibility columns exist in pnl_reports table for older DB files.

    Uses AsyncEngine.run_sync to execute synchronous inspection and ALTER
    statements on a sync connection. This avoids calling `inspect` on an
    AsyncEngine (which raises NoInspectionAvailable).
    """

    needed = {
        'total_pnl': 'REAL',
        'fees': 'REAL',
        'trades_count': 'INTEGER',
        'win_rate': 'REAL',
    }

    async with async_engine.begin() as conn:
        def _sync_inspect_and_alter(sync_conn):
            # sync_conn is a SQLAlchemy Connection (synchronous) provided by run_sync
            try:
                insp = inspect(sync_conn)
                try:
                    cols = {c['name'] for c in insp.get_columns('pnl_reports')}
                except Exception:
                    # Table probably doesn't exist yet; nothing to do here.
                    logging.getLogger(__name__).debug("pnl_reports table not present yet")
                    return

                for name, col_type in needed.items():
                    if name not in cols:
                        logging.getLogger(__name__).info(f"Adding missing column {name} to pnl_reports")
                        try:
                            sync_conn.execute(text(f"ALTER TABLE pnl_reports ADD COLUMN {name} {col_type} DEFAULT 0"))
                        except Exception:
                            logging.getLogger(__name__).exception(f"Failed to add column {name} to pnl_reports")
            except Exception:
                logging.getLogger(__name__).exception("Error during sync inspection for pnl columns")

        # run the synchronous inspection/alter logic on the connection's thread
        await conn.run_sync(_sync_inspect_and_alter)

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
