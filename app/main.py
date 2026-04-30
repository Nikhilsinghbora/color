"""FastAPI application factory.

Wires together all API routers, middleware, database sessions, Redis
connection pool, and lifecycle event handlers for the Color Prediction
Game platform.

Requirements: 13.1, 13.5
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level Redis connection pool — initialised during app startup.
redis_pool: aioredis.ConnectionPool | None = None


def get_redis_pool() -> aioredis.ConnectionPool:
    """Return the shared Redis connection pool.

    Raises RuntimeError if the pool has not been initialised yet (i.e. the
    application has not started).
    """
    if redis_pool is None:
        raise RuntimeError("Redis connection pool is not initialised")
    return redis_pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown of DB engine, Redis pool, and WS manager."""
    global redis_pool

    from app.models.base import engine
    from app.services.ws_manager import ws_manager

    # --- Startup ---
    # Initialise Redis connection pool (Requirement 13.5)
    redis_pool = aioredis.ConnectionPool.from_url(
        settings.redis_url, decode_responses=True,
    )
    logger.info("Redis connection pool initialised")

    # Start WebSocket manager (Redis pub/sub listener + heartbeat)
    await ws_manager.start()
    logger.info("WebSocket manager started")

    yield

    # --- Shutdown ---
    await ws_manager.shutdown()
    logger.info("WebSocket manager shut down")

    # Close Redis pool
    await redis_pool.aclose()
    redis_pool = None
    logger.info("Redis connection pool closed")

    # Dispose SQLAlchemy async engine (Requirement 13.5)
    await engine.dispose()
    logger.info("Database engine disposed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Color Prediction Game",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    _register_middleware(app)
    _register_routers(app)
    _register_health_check(app)

    return app


def _register_middleware(app: FastAPI) -> None:
    """Register application middleware."""
    from app.middleware.auth import RecentAuthMiddleware
    from app.middleware.cors import configure_cors
    from app.middleware.error_handler import register_exception_handlers
    from app.middleware.rate_limiter import RateLimitMiddleware

    # Exception handlers (must be registered before middleware)
    register_exception_handlers(app)

    # CORS (added as outermost middleware — Requirement 12.7)
    configure_cors(app)

    # Rate limiting per player session (Requirement 12.3)
    app.add_middleware(RateLimitMiddleware)

    # Re-authentication for sensitive endpoints (Requirement 12.4)
    app.add_middleware(RecentAuthMiddleware)


def _register_routers(app: FastAPI) -> None:
    """Register all API routers."""
    from app.api.admin import router as admin_router
    from app.api.auth import router as auth_router
    from app.api.game import router as game_router
    from app.api.leaderboard import router as leaderboard_router
    from app.api.responsible_gambling import router as responsible_gambling_router
    from app.api.social import router as social_router
    from app.api.wallet import router as wallet_router
    from app.api.websocket import router as ws_router

    app.include_router(auth_router)
    app.include_router(wallet_router)
    app.include_router(game_router)
    app.include_router(leaderboard_router)
    app.include_router(social_router)
    app.include_router(responsible_gambling_router)
    app.include_router(admin_router)
    app.include_router(ws_router)


def _register_health_check(app: FastAPI) -> None:
    """Register health check endpoint (Requirement 13.5)."""

    @app.get("/api/v1/health")
    async def health_check() -> JSONResponse:
        """Return service health including DB and Redis connectivity."""
        from app.models.base import engine

        health: dict = {"status": "ok", "db": "ok", "redis": "ok"}
        status_code = 200

        # Check database connectivity
        try:
            async with engine.connect() as conn:
                await conn.execute(
                    __import__("sqlalchemy").text("SELECT 1"),
                )
        except Exception:
            health["db"] = "unavailable"
            health["status"] = "degraded"
            status_code = 503

        # Check Redis connectivity
        try:
            pool = get_redis_pool()
            client = aioredis.Redis(connection_pool=pool)
            await client.ping()
        except Exception:
            health["redis"] = "unavailable"
            health["status"] = "degraded"
            status_code = 503

        return JSONResponse(content=health, status_code=status_code)


app = create_app()
