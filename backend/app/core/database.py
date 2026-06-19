"""
app/core/database.py
Async SQLAlchemy engine and session factory.
All database access goes through the async session — no sync calls.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _build_engine() -> AsyncEngine:
    """Build the async engine with connection pool settings."""
    return create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_pre_ping=True,  # Verify connections before use (avoids stale conn errors)
        echo=settings.db_echo,
    )


# Module-level engine and session factory
engine: AsyncEngine = _build_engine()

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Allows accessing attributes after commit without re-query
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async DB session.
    Commits on success, rolls back on exception, always closes.

    Usage:
        @router.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
