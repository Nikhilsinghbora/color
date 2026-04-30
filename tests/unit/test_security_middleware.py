"""Unit tests for security middleware (rate limiter, CORS, auth)."""

import time
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from jose import jwt

from app.config import settings
from app.exceptions import RateLimitExceededError
from app.middleware.auth import RecentAuthMiddleware, _RECENT_AUTH_MAX_AGE
from app.middleware.rate_limiter import RateLimitMiddleware, RATE_LIMIT, WINDOW_SECONDS


def _make_token(player_id: str | None = None, iat: float | None = None, token_type: str = "access") -> str:
    """Create a JWT token for testing."""
    payload = {"type": token_type}
    if player_id is not None:
        payload["sub"] = player_id
    if iat is not None:
        payload["iat"] = iat
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


class FakeRequest:
    """Minimal request stub for middleware tests."""

    def __init__(self, path: str = "/api/v1/game", authorization: str | None = None):
        hdrs = {}
        if authorization is not None:
            hdrs["authorization"] = authorization
        self.headers = hdrs

        class _URL:
            def __init__(self, p):
                self.path = p
        self.url = _URL(path)


class FakeResponse:
    status_code = 200


# ---------------------------------------------------------------------------
# Rate limiter tests
# ---------------------------------------------------------------------------

class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""

    @pytest.mark.asyncio
    async def test_unauthenticated_request_skips_rate_limit(self):
        """Requests without a valid JWT should pass through without rate limiting."""
        redis_mock = AsyncMock()
        middleware = RateLimitMiddleware(app=AsyncMock(), redis=redis_mock)

        request = FakeRequest(authorization="InvalidHeader")
        call_next = AsyncMock(return_value=FakeResponse())

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        redis_mock.incr.assert_not_called()

    @pytest.mark.asyncio
    async def test_authenticated_request_increments_counter(self):
        """Valid JWT requests should increment the Redis counter."""
        pid = str(uuid4())
        token = _make_token(player_id=pid)

        redis_mock = AsyncMock()
        redis_mock.incr.return_value = 1
        middleware = RateLimitMiddleware(app=AsyncMock(), redis=redis_mock)

        request = FakeRequest(authorization=f"Bearer {token}")
        call_next = AsyncMock(return_value=FakeResponse())

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        redis_mock.incr.assert_called_once_with(f"rate_limit:{pid}")
        redis_mock.expire.assert_called_once_with(f"rate_limit:{pid}", WINDOW_SECONDS)

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_raises(self):
        """Exceeding 100 requests should raise RateLimitExceededError."""
        pid = str(uuid4())
        token = _make_token(player_id=pid)

        redis_mock = AsyncMock()
        redis_mock.incr.return_value = RATE_LIMIT + 1
        redis_mock.ttl.return_value = 42
        middleware = RateLimitMiddleware(app=AsyncMock(), redis=redis_mock)

        request = FakeRequest(authorization=f"Bearer {token}")
        call_next = AsyncMock(return_value=FakeResponse())

        with pytest.raises(RateLimitExceededError) as exc_info:
            await middleware.dispatch(request, call_next)

        assert exc_info.value.retry_after == 42

    @pytest.mark.asyncio
    async def test_no_bearer_prefix_skips(self):
        """Authorization header without 'Bearer' prefix should skip rate limiting."""
        redis_mock = AsyncMock()
        middleware = RateLimitMiddleware(app=AsyncMock(), redis=redis_mock)

        request = FakeRequest(authorization="Basic abc123")
        call_next = AsyncMock(return_value=FakeResponse())

        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        redis_mock.incr.assert_not_called()


# ---------------------------------------------------------------------------
# Auth middleware tests
# ---------------------------------------------------------------------------

class TestRecentAuthMiddleware:
    """Tests for RecentAuthMiddleware."""

    @pytest.mark.asyncio
    async def test_non_sensitive_path_passes_through(self):
        """Non-sensitive paths should not be checked."""
        middleware = RecentAuthMiddleware(app=AsyncMock())

        request = FakeRequest(path="/api/v1/game")
        call_next = AsyncMock(return_value=FakeResponse())

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_sensitive_path_with_fresh_token_passes(self):
        """Sensitive path with a recently issued JWT should pass."""
        token = _make_token(player_id=str(uuid4()), iat=time.time())
        middleware = RecentAuthMiddleware(app=AsyncMock())

        request = FakeRequest(path="/api/v1/wallet/balance", authorization=f"Bearer {token}")
        call_next = AsyncMock(return_value=FakeResponse())

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_sensitive_path_with_stale_token_rejects(self):
        """Sensitive path with a JWT older than 10 minutes should be rejected."""
        from fastapi import HTTPException

        stale_iat = time.time() - _RECENT_AUTH_MAX_AGE - 60
        token = _make_token(player_id=str(uuid4()), iat=stale_iat)
        middleware = RecentAuthMiddleware(app=AsyncMock())

        request = FakeRequest(path="/api/v1/wallet/deposit", authorization=f"Bearer {token}")
        call_next = AsyncMock(return_value=FakeResponse())

        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(request, call_next)

        assert exc_info.value.status_code == 401
        assert "Re-authentication required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_sensitive_path_no_auth_passes_through(self):
        """Sensitive path without auth header lets downstream handle it."""
        middleware = RecentAuthMiddleware(app=AsyncMock())

        request = FakeRequest(path="/api/v1/wallet/balance")
        call_next = AsyncMock(return_value=FakeResponse())

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_sensitive_path_no_iat_rejects(self):
        """Sensitive path with JWT missing iat claim should be rejected."""
        from fastapi import HTTPException

        token = _make_token(player_id=str(uuid4()))  # no iat
        middleware = RecentAuthMiddleware(app=AsyncMock())

        request = FakeRequest(path="/api/v1/account/settings", authorization=f"Bearer {token}")
        call_next = AsyncMock(return_value=FakeResponse())

        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(request, call_next)

        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# CORS configuration test
# ---------------------------------------------------------------------------

class TestConfigureCors:
    """Tests for configure_cors."""

    def test_configure_cors_adds_middleware(self):
        """configure_cors should add CORSMiddleware to the app."""
        from unittest.mock import MagicMock
        from app.middleware.cors import configure_cors

        app_mock = MagicMock()
        configure_cors(app_mock)

        app_mock.add_middleware.assert_called_once()
        args, kwargs = app_mock.add_middleware.call_args
        from fastapi.middleware.cors import CORSMiddleware
        assert args[0] is CORSMiddleware
        assert kwargs["allow_origins"] == settings.cors_allowed_origins
        assert kwargs["allow_credentials"] is True
