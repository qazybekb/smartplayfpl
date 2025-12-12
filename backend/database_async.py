"""
Async SQLAlchemy database adapter for SmartPlayFPL.

This module provides async database access using SQLAlchemy 2.0 async features.
Use this for new async endpoints that need database access.

Migration Guide:
1. Replace: from database import SessionLocal, get_db
   With:     from database_async import get_async_db, AsyncSessionLocal

2. Change endpoint signature:
   Before: async def endpoint(db: Session = Depends(get_db)):
   After:  async def endpoint(db: AsyncSession = Depends(get_async_db)):

3. Use async query methods:
   Before: db.query(Model).filter(...).all()
   After:  result = await db.execute(select(Model).filter(...))
           items = result.scalars().all()

4. Commit changes:
   Before: db.commit()
   After:  await db.commit()
"""

import os
import logging
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy import text

logger = logging.getLogger("smartplayfpl.database")

# =============================================================================
# ASYNC DATABASE CONFIGURATION
# =============================================================================

# Convert sync URL to async URL
def _get_async_url(sync_url: str) -> str:
    """Convert synchronous database URL to async equivalent."""
    if sync_url.startswith("sqlite:///"):
        # SQLite: sqlite:/// -> sqlite+aiosqlite:///
        return sync_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    elif sync_url.startswith("postgresql://"):
        # PostgreSQL: postgresql:// -> postgresql+asyncpg://
        return sync_url.replace("postgresql://", "postgresql+asyncpg://")
    elif sync_url.startswith("mysql://"):
        # MySQL: mysql:// -> mysql+aiomysql://
        return sync_url.replace("mysql://", "mysql+aiomysql://")
    return sync_url


# Get database URL
SYNC_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./smartplayfpl.db")
ASYNC_DATABASE_URL = _get_async_url(SYNC_DATABASE_URL)

# Connection pool settings
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))


# =============================================================================
# ASYNC ENGINE & SESSION
# =============================================================================

# Create async engine
if "sqlite" in ASYNC_DATABASE_URL:
    # SQLite async doesn't support pool settings the same way
    async_engine = create_async_engine(
        ASYNC_DATABASE_URL,
        echo=os.getenv("DB_ECHO", "false").lower() == "true",
    )
    logger.info("Async SQLite engine created")
else:
    # PostgreSQL/MySQL with full connection pooling
    async_engine = create_async_engine(
        ASYNC_DATABASE_URL,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_timeout=POOL_TIMEOUT,
        pool_recycle=POOL_RECYCLE,
        pool_pre_ping=True,
        echo=os.getenv("DB_ECHO", "false").lower() == "true",
    )
    logger.info(f"Async database pool configured: size={POOL_SIZE}")


# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# =============================================================================
# DEPENDENCY INJECTION
# =============================================================================

async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for async database sessions.

    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_async_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for async database sessions.

    Usage:
        async with get_async_session() as db:
            result = await db.execute(select(Item))
            items = result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# =============================================================================
# HEALTH CHECK
# =============================================================================

async def check_database_health() -> dict:
    """
    Check async database connectivity.

    Returns:
        dict with 'ok' status and latency
    """
    import time

    try:
        start = time.time()
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        latency_ms = (time.time() - start) * 1000

        return {
            "ok": True,
            "latency_ms": round(latency_ms, 2),
            "driver": "async",
        }
    except Exception as e:
        logger.error(f"Async database health check failed: {e}")
        return {
            "ok": False,
            "error": str(e),
            "driver": "async",
        }


# =============================================================================
# MIGRATION HELPERS
# =============================================================================

async def init_async_db():
    """
    Create all tables using async engine.
    Call during app startup if using async-first approach.
    """
    from database import Base

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Async database tables initialized")


async def dispose_async_engine():
    """
    Dispose of async engine connections.
    Call during app shutdown.
    """
    await async_engine.dispose()
    logger.info("Async database engine disposed")


# =============================================================================
# QUERY HELPERS
# =============================================================================

# Example query patterns for migration reference:

"""
# SELECT queries:
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Simple select
result = await db.execute(select(Player))
players = result.scalars().all()

# Select with filter
result = await db.execute(
    select(Player).where(Player.position == "MID")
)
player = result.scalar_one_or_none()

# Select with ordering and limit
result = await db.execute(
    select(Player)
    .order_by(Player.total_points.desc())
    .limit(10)
)
top_players = result.scalars().all()

# Select with eager loading
result = await db.execute(
    select(Team).options(selectinload(Team.players))
)
teams = result.scalars().all()


# INSERT/UPDATE/DELETE:
from sqlalchemy import update, delete

# Insert
new_player = Player(name="Test", position="FWD")
db.add(new_player)
await db.commit()
await db.refresh(new_player)

# Update
await db.execute(
    update(Player)
    .where(Player.id == player_id)
    .values(status="injured")
)
await db.commit()

# Delete
await db.execute(
    delete(Player).where(Player.id == player_id)
)
await db.commit()


# Bulk operations:
from sqlalchemy.dialects.postgresql import insert

# Bulk upsert (PostgreSQL)
stmt = insert(Player).values(players_data)
stmt = stmt.on_conflict_do_update(
    index_elements=['id'],
    set_={
        'total_points': stmt.excluded.total_points,
        'updated_at': datetime.utcnow(),
    }
)
await db.execute(stmt)
await db.commit()
"""
