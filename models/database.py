from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData, text
import os
from typing import AsyncGenerator

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./trading_system.db")

# Create async engine with optimized settings for faster startup
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=False,  # Disable ping for faster startup
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
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
    """Initialize database tables (optimized for fast startup)"""
    # Skip heavy initialization if database already exists and is populated
    import os
    db_file = "trading_system.db"
    if os.path.exists(db_file) and os.path.getsize(db_file) > 1000:
        # Database exists and appears to be populated, skip heavy checks
        return
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Only run column checks on first-time setup or small databases
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
