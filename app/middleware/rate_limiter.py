"""Rate limiting middleware using Redis counters.

Requirement 12.3: 100 requests per minute per player session.
"""

from __future__ import annotations

from jose import JWTError, jwt
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.config import settings
from app.exceptions import RateLimitExceededError

RATE_LIMIT = 100
WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Enforce per-player rate limiting via Redis INCR + EXPIRE."""

    def __init__(self, app: ASGIApp, redis: Redis | None = None) -> None:
        super().__init__(app)
        self._redis = redis

    async def _get_redis(self) -> Redis:
        if self._redis is None:
            self._redis = Redis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    def _extract_player_id(self, request: Request) -> str | None:
        """Extract player_id from JWT in Authorization header.

        Returns None if no valid JWT is present (let auth handle rejection).
        """
        auth_header = request.headers.get("authorization", "")
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        try:
            payload = jwt.decode(
                parts[1],
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
        except JWTError:
            return None

        if payload.get("type") != "access":
            return None

        return payload.get("sub")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        player_id = self._extract_player_id(request)

        # Skip rate limiting for unauthenticated requests
        if player_id is None:
            return await call_next(request)

        redis = await self._get_redis()
        key = f"rate_limit:{player_id}"

        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, WINDOW_SECONDS)

        if current > RATE_LIMIT:
            ttl = await redis.ttl(key)
            retry_after = max(ttl, 1)
            raise RateLimitExceededError(retry_after=retry_after)

        return await call_next(request)
