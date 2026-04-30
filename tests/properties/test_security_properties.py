"""Property-based tests for security features.

Uses Hypothesis to generate random test data for verifying rate limiting
and audit trail invariants.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.exceptions import RateLimitExceededError
from app.middleware.rate_limiter import RateLimitMiddleware, RATE_LIMIT, WINDOW_SECONDS
from app.models.audit import AuditEventType, AuditTrail
from app.models.player import Player
from app.services import audit_service
from app.services.audit_service import create_audit_entry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jwt(player_id: str) -> str:
    """Create a valid JWT access token for testing."""
    return jwt.encode(
        {"sub": player_id, "type": "access"},
        app_settings.jwt_secret_key,
        algorithm=app_settings.jwt_algorithm,
    )


class FakeRequest:
    """Minimal request object for rate limiter middleware testing."""

    def __init__(self, token: str):
        self.headers = {"authorization": f"Bearer {token}"}


async def _create_player(session: AsyncSession) -> Player:
    """Create a fresh player for each Hypothesis iteration."""
    player = Player(
        id=uuid4(),
        email=f"{uuid4().hex[:8]}@test.com",
        username=f"user-{uuid4().hex[:8]}",
        password_hash="hashed",
    )
    session.add(player)
    await session.flush()
    return player


# ---------------------------------------------------------------------------
# Property 22: Rate limiting enforcement
# More than 100 requests in 60s window returns 429; requests within limit
# processed normally.
# Validates: Requirements 12.3
# ---------------------------------------------------------------------------


class TestProperty22RateLimitingEnforcement:
    """**Validates: Requirements 12.3**"""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(num_requests=st.integers(min_value=1, max_value=100))
    async def test_requests_within_limit_processed_normally(self, num_requests):
        """For any N requests where N <= 100, the middleware SHALL call
        call_next and return a 200 response."""
        player_id = str(uuid4())
        token = _make_jwt(player_id)
        request = FakeRequest(token)

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=num_requests)
        mock_redis.expire = AsyncMock()
        mock_redis.ttl = AsyncMock(return_value=WINDOW_SECONDS)

        mock_response = AsyncMock()
        mock_response.status_code = 200
        call_next = AsyncMock(return_value=mock_response)

        middleware = RateLimitMiddleware(app=AsyncMock(), redis=mock_redis)
        response = await middleware.dispatch(request, call_next)

        call_next.assert_called_once_with(request)
        assert response.status_code == 200

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(num_requests=st.integers(min_value=101, max_value=500))
    async def test_requests_over_limit_rejected(self, num_requests):
        """For any N requests where N > 100, the middleware SHALL raise
        RateLimitExceededError."""
        player_id = str(uuid4())
        token = _make_jwt(player_id)
        request = FakeRequest(token)

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=num_requests)
        mock_redis.expire = AsyncMock()
        mock_redis.ttl = AsyncMock(return_value=30)

        call_next = AsyncMock()

        middleware = RateLimitMiddleware(app=AsyncMock(), redis=mock_redis)

        with pytest.raises(RateLimitExceededError):
            await middleware.dispatch(request, call_next)

        call_next.assert_not_called()


# ---------------------------------------------------------------------------
# Property 23: Audit trail creation
# Every auditable event creates an immutable audit entry with event_type,
# actor_id, timestamp, and details. The audit trail is append-only.
# Validates: Requirements 12.5
# ---------------------------------------------------------------------------


class TestProperty23AuditTrailCreation:
    """**Validates: Requirements 12.5**"""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        event_type=st.sampled_from(list(AuditEventType)),
        details=st.fixed_dictionaries({"key": st.text(min_size=1, max_size=20)}),
    )
    async def test_audit_entry_has_required_fields(self, session, event_type, details):
        """For any auditable event, the created audit entry SHALL contain
        non-null id, created_at, correct event_type, actor_id, and details."""
        player = await _create_player(session)

        entry = await create_audit_entry(
            session,
            event_type=event_type,
            actor_id=player.id,
            details=details,
        )

        assert entry.id is not None
        assert entry.created_at is not None
        assert entry.event_type == event_type
        assert entry.actor_id == player.id
        assert entry.details == details

    def test_audit_service_has_no_update_function(self):
        """The audit service SHALL NOT expose an update function (append-only)."""
        assert not hasattr(audit_service, "update_audit_entry")

    def test_audit_service_has_no_delete_function(self):
        """The audit service SHALL NOT expose a delete function (append-only)."""
        assert not hasattr(audit_service, "delete_audit_entry")
