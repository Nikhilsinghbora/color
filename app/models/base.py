"""SQLAlchemy base configuration with async engine setup."""

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models."""
    pass


async def get_session() -> AsyncSession:
    """Yield an async database session."""
    async with async_session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Celery-safe session helper
# ---------------------------------------------------------------------------
# The global ``engine`` is bound to whatever event loop existed at import
# time.  Celery tasks run ``_run_async`` which creates a *new* event loop
# each time, so the global engine's connection pool is unusable there
# (asyncpg raises "another operation is in progress").
#
# ``celery_session()`` creates a **per-call** engine+session that is
# scoped to the current event loop and disposed afterwards.
# ---------------------------------------------------------------------------

_celery_engine = None
_celery_session_factory = None


def _get_celery_engine():
    """Return a module-level engine for Celery, creating it lazily.

    This engine is created on first use (inside the Celery worker's
    event loop) and reused for the lifetime of that loop invocation.
    The caller is responsible for disposing it when the loop ends.
    """
    global _celery_engine, _celery_session_factory
    if _celery_engine is None:
        _celery_engine = create_async_engine(
            settings.database_url, echo=False, pool_size=5, max_overflow=0,
        )
        _celery_session_factory = async_sessionmaker(
            _celery_engine, class_=AsyncSession, expire_on_commit=False,
        )
    return _celery_engine, _celery_session_factory


async def dispose_celery_engine():
    """Dispose the Celery engine, releasing all pooled connections."""
    global _celery_engine, _celery_session_factory
    if _celery_engine is not None:
        await _celery_engine.dispose()
        _celery_engine = None
        _celery_session_factory = None


@asynccontextmanager
async def celery_session():
    """Create an async session for Celery tasks.

    Uses a lazily-created engine that is bound to the current event loop.
    """
    _engine, factory = _get_celery_engine()
    async with factory() as session:
        yield session
