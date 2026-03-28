"""
SARC360 ERP - Async Database Engine & Session Factory
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# ── Async Engine ─────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,          # Log SQL in development
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,           # Detect stale connections
    pool_recycle=3600,            # Recycle connections every hour
)

# ── Session Factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,       # Keep objects usable after commit
    autoflush=False,
)


# ── Declarative Base ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


# ── FastAPI Dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an async DB session per request.
    Usage:
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...
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


async def create_all_tables() -> None:
    """Create all tables (dev/test only — use Alembic in production)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all_tables() -> None:
    """Drop all tables (test teardown only)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
