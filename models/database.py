from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData, text
from sqlalchemy.pool import NullPool
import os
from typing import AsyncGenerator

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./trading_system.db")

# Determine if using PostgreSQL or SQLite
is_postgres = "postgresql" in DATABASE_URL
is_sqlite = "sqlite" in DATABASE_URL

# Create async engine with database-specific configuration
if is_postgres:
    # PostgreSQL: Use connection pooling for optimal performance
    # For 50+ concurrent requests: 40 persistent + 60 overflow = 100 total connections
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        pool_size=40,  # 40 persistent connections
        max_overflow=60,  # Up to 100 total connections
        pool_timeout=10,  # Wait only 10s (fail fast if pool exhausted)
        pool_recycle=3600,  # Recycle connections every hour
        pool_pre_ping=True,  # Verify connections before use
    )
elif is_sqlite:
    # SQLite: Use NullPool (no pooling) to avoid locking issues
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        poolclass=NullPool,  # No pooling for SQLite
        connect_args={
            "check_same_thread": False,
            "timeout": 60.0  # 60 second timeout for lock acquisition
        }
    )
else:
    # Fallback: No special pooling
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        future=True,
        poolclass=NullPool
    )

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Create base class for models using modern SQLAlchemy 2.0+ pattern
class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    """Initialize or migrate database tables (lightweight and idempotent)."""
    async with engine.begin() as conn:
        # Always ensure all declared models are created (checkfirst prevents heavy work)
        await conn.run_sync(Base.metadata.create_all)

        # Lightweight column backfills for legacy installs (SQLite only)
        try:
            if engine.url.get_backend_name().startswith("sqlite"):
                # Watchlist legacy columns
                result = await conn.execute(text("PRAGMA table_info('watchlist')"))
                columns = {row[1] for row in result.fetchall()}
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
