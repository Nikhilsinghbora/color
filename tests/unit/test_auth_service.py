"""Unit tests for the authentication service.

Validates: Requirements 1.2, 1.3, 1.4, 1.6
"""

from datetime import timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import AccountLockedError
from app.models.player import Player
from app.services.auth_service import (
    TokenPair,
    _hash_password,
    _verify_password,
    authenticate,
    check_account_lock,
    refresh_token,
    register_player,
    request_password_reset,
    reset_password,
    _create_token,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_redis_mock(counter: dict | None = None):
    """Return an AsyncMock Redis client that tracks an incr counter."""
    if counter is None:
        counter = {"value": 0}
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.delete = AsyncMock()
    mock.expire = AsyncMock()
    mock.aclose = AsyncMock()

    async def _incr(key):
        counter["value"] += 1
        return counter["value"]

    mock.incr = AsyncMock(side_effect=_incr)
    return mock, counter


async def _create_player(session: AsyncSession, email="user@example.com",
                         username="testuser", password="Str0ngP@ss!") -> Player:
    """Register a player via the service and return the Player object."""
    redis_mock, _ = _make_redis_mock()
    with patch("app.services.auth_service._get_redis", return_value=redis_mock):
        player = await register_player(session, email, username, password)
    return player


# ---------------------------------------------------------------------------
# 1. Login flow with valid / invalid credentials
# ---------------------------------------------------------------------------

class TestLoginFlow:
    """Test successful and failed login scenarios."""

    async def test_successful_login_returns_token_pair(self, session):
        """Successful login returns a TokenPair with access_token, refresh_token, expires_in."""
        player = await _create_player(session)
        redis_mock, _ = _make_redis_mock()
        with patch("app.services.auth_service._get_redis", return_value=redis_mock):
            result = await authenticate(session, "user@example.com", "Str0ngP@ss!")

        assert isinstance(result, TokenPair)
        assert result.access_token
        assert result.refresh_token
        assert result.expires_in == settings.jwt_access_token_expire_minutes * 60

    async def test_login_wrong_password_raises(self, session):
        """Login with wrong password raises ValueError."""
        await _create_player(session)
        redis_mock, _ = _make_redis_mock()
        with patch("app.services.auth_service._get_redis", return_value=redis_mock):
            with pytest.raises(ValueError, match="Invalid email or password"):
                await authenticate(session, "user@example.com", "WrongPassword!")

    async def test_login_nonexistent_email_raises(self, session):
        """Login with non-existent email raises ValueError."""
        redis_mock, _ = _make_redis_mock()
        with patch("app.services.auth_service._get_redis", return_value=redis_mock):
            with pytest.raises(ValueError, match="Invalid email or password"):
                await authenticate(session, "nobody@example.com", "Whatever1!")

    async def test_successful_login_resets_failed_counter(self, session):
        """Successful login calls Redis delete to reset the failed login counter."""
        player = await _create_player(session)
        redis_mock, _ = _make_redis_mock()
        with patch("app.services.auth_service._get_redis", return_value=redis_mock):
            await authenticate(session, "user@example.com", "Str0ngP@ss!")

        # delete should have been called (to reset failed logins)
        redis_mock.delete.assert_called()


# ---------------------------------------------------------------------------
# 2. Account locking after 3 failed attempts and 15-minute lockout
# ---------------------------------------------------------------------------

class TestAccountLocking:
    """Test account lock behaviour after repeated failed logins."""

    async def test_account_locked_after_3_failures(self, session):
        """After 3 failed login attempts, AccountLockedError is raised."""
        await _create_player(session)
        counter: dict = {"value": 0}
        redis_mock, counter = _make_redis_mock(counter)

        with patch("app.services.auth_service._get_redis", return_value=redis_mock):
            # First two failures raise ValueError
            for _ in range(2):
                with pytest.raises(ValueError):
                    await authenticate(session, "user@example.com", "bad")

            # Third failure triggers AccountLockedError
            with pytest.raises(AccountLockedError):
                await authenticate(session, "user@example.com", "bad")

    async def test_check_account_lock_returns_true_when_locked(self, session):
        """check_account_lock returns True when counter >= 3."""
        player = await _create_player(session)
        redis_mock, _ = _make_redis_mock()
        redis_mock.get = AsyncMock(return_value="3")

        with patch("app.services.auth_service._get_redis", return_value=redis_mock):
            assert await check_account_lock(player.id) is True

    async def test_check_account_lock_returns_false_when_not_locked(self, session):
        """check_account_lock returns False when counter < 3 or absent."""
        player = await _create_player(session)
        redis_mock, _ = _make_redis_mock()
        redis_mock.get = AsyncMock(return_value=None)

        with patch("app.services.auth_service._get_redis", return_value=redis_mock):
            assert await check_account_lock(player.id) is False

    async def test_locked_account_cannot_authenticate(self, session):
        """A locked account raises AccountLockedError on authenticate."""
        await _create_player(session)
        redis_mock, _ = _make_redis_mock()
        # Simulate already-locked state
        redis_mock.get = AsyncMock(return_value="3")

        with patch("app.services.auth_service._get_redis", return_value=redis_mock):
            with pytest.raises(AccountLockedError):
                await authenticate(session, "user@example.com", "Str0ngP@ss!")


# ---------------------------------------------------------------------------
# 3. Password reset token generation and consumption
# ---------------------------------------------------------------------------

class TestPasswordReset:
    """Test password reset request and consumption."""

    async def test_request_reset_valid_email_no_error(self, session):
        """request_password_reset with a valid email does not raise."""
        await _create_player(session)
        await request_password_reset(session, "user@example.com")

    async def test_request_reset_nonexistent_email_silent(self, session):
        """request_password_reset with unknown email silently returns."""
        await request_password_reset(session, "ghost@example.com")

    async def test_reset_password_with_valid_token(self, session):
        """reset_password with a valid token updates the password hash."""
        player = await _create_player(session)
        old_hash = player.password_hash

        # Create a valid password_reset token
        token = _create_token(player.id, "password_reset", timedelta(hours=1))
        await reset_password(session, token, "NewStr0ng!Pass")

        await session.refresh(player)
        assert player.password_hash != old_hash
        assert _verify_password("NewStr0ng!Pass", player.password_hash)

    async def test_reset_password_invalid_token_raises(self, session):
        """reset_password with an invalid/expired token raises ValueError."""
        with pytest.raises(ValueError, match="Invalid reset token"):
            await reset_password(session, "not.a.valid.token", "NewPass1!")

    async def test_reset_password_wrong_token_type_raises(self, session):
        """reset_password with a non-reset token type raises ValueError."""
        player = await _create_player(session)
        # Issue an access token instead of a password_reset token
        access_token = _create_token(player.id, "access", timedelta(minutes=30))
        with pytest.raises(ValueError, match="not a password reset token"):
            await reset_password(session, access_token, "NewPass1!")


# ---------------------------------------------------------------------------
# 4. Session timeout after 30 minutes of inactivity
# ---------------------------------------------------------------------------

class TestSessionTimeout:
    """Test JWT token expiry and refresh behaviour."""

    async def test_access_token_has_30_minute_expiry(self, session):
        """JWT access token exp claim is ~30 minutes from iat."""
        player = await _create_player(session)
        redis_mock, _ = _make_redis_mock()
        with patch("app.services.auth_service._get_redis", return_value=redis_mock):
            tokens = await authenticate(session, "user@example.com", "Str0ngP@ss!")

        payload = jwt.decode(
            tokens.access_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        assert payload["type"] == "access"
        expiry_seconds = payload["exp"] - payload["iat"]
        assert expiry_seconds == settings.jwt_access_token_expire_minutes * 60

    async def test_expired_access_token_rejected_as_refresh(self, session):
        """An access token (even if valid) is rejected by refresh_token."""
        player = await _create_player(session)
        redis_mock, _ = _make_redis_mock()
        with patch("app.services.auth_service._get_redis", return_value=redis_mock):
            tokens = await authenticate(session, "user@example.com", "Str0ngP@ss!")

        with pytest.raises(ValueError, match="not a refresh token"):
            await refresh_token(tokens.access_token)

    async def test_refresh_with_valid_refresh_token(self, session):
        """refresh_token with a valid refresh token returns a new TokenPair."""
        player = await _create_player(session)
        redis_mock, _ = _make_redis_mock()
        with patch("app.services.auth_service._get_redis", return_value=redis_mock):
            tokens = await authenticate(session, "user@example.com", "Str0ngP@ss!")

        new_tokens = await refresh_token(tokens.refresh_token)
        assert isinstance(new_tokens, TokenPair)
        assert new_tokens.access_token
        assert new_tokens.refresh_token
        assert new_tokens.expires_in == settings.jwt_access_token_expire_minutes * 60
        # Verify the new access token decodes with correct claims
        payload = jwt.decode(
            new_tokens.access_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        assert payload["sub"] == str(player.id)
        assert payload["type"] == "access"
