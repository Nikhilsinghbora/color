"""Authentication service for player registration, login, and password management.

Provides standalone async functions for all auth operations, following the same
pattern as wallet_service.py. Uses passlib bcrypt for password hashing,
python-jose for JWT tokens, and Redis for account lock tracking.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import NamedTuple
from uuid import UUID, uuid4

import bcrypt
import redis.asyncio as aioredis
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import AccountLockedError
from app.models.player import Player, Wallet

# Bcrypt cost factor (rounds)
BCRYPT_ROUNDS = 12

# Redis key patterns
_FAILED_LOGIN_KEY = "player:{player_id}:failed_logins"
_FAILED_LOGIN_TTL = 900  # 15 minutes

# Account lock threshold
_MAX_FAILED_ATTEMPTS = 3


class TokenPair(NamedTuple):
    """JWT access + refresh token pair."""

    access_token: str
    refresh_token: str
    expires_in: int  # access token expiry in seconds


def _get_redis() -> aioredis.Redis:
    """Create a Redis client from settings."""
    return aioredis.from_url(settings.redis_url, decode_responses=True)


def _hash_password(password: str) -> str:
    """Hash a password using bcrypt with cost factor 12."""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def _verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def _create_token(player_id: UUID, token_type: str, expires_delta: timedelta) -> str:
    """Create a signed JWT token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(player_id),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _issue_token_pair(player_id: UUID) -> TokenPair:
    """Issue an access + refresh token pair for a player."""
    access_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    refresh_expires = timedelta(days=settings.jwt_refresh_token_expire_days)

    access_token = _create_token(player_id, "access", access_expires)
    refresh_token = _create_token(player_id, "refresh", refresh_expires)

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


async def register_player(
    session: AsyncSession,
    email: str,
    username: str,
    password: str,
) -> Player:
    """Create a new player account with a zero-balance wallet.

    Hashes the password with bcrypt (cost 12), creates the player record,
    initializes a wallet with zero balance, and queues a verification email.

    Args:
        session: Async database session.
        email: Player's email address.
        username: Unique username.
        password: Plain-text password (will be hashed).

    Returns:
        The newly created Player instance.
    """
    password_hash = _hash_password(password)

    player = Player(
        id=uuid4(),
        email=email,
        username=username,
        password_hash=password_hash,
    )
    session.add(player)
    await session.flush()

    # Initialize wallet with zero balance
    wallet = Wallet(
        id=uuid4(),
        player_id=player.id,
        balance=Decimal("0.00"),
    )
    session.add(wallet)
    await session.flush()

    from app.tasks.email_tasks import send_verification_email
    send_verification_email.delay(str(player.id), player.email)

    return player


async def check_account_lock(player_id: UUID) -> bool:
    """Check if a player's account is locked due to failed login attempts.

    Reads the failed login counter from Redis. Returns True if the counter
    has reached or exceeded the threshold (3 attempts), meaning the account
    is locked for the remaining TTL of the key (up to 15 minutes).

    Args:
        player_id: The player's UUID.

    Returns:
        True if the account is currently locked, False otherwise.
    """
    r = _get_redis()
    try:
        key = _FAILED_LOGIN_KEY.format(player_id=player_id)
        count = await r.get(key)
        if count is not None and int(count) >= _MAX_FAILED_ATTEMPTS:
            return True
        return False
    finally:
        await r.aclose()


async def _increment_failed_logins(player_id: UUID) -> int:
    """Increment the failed login counter in Redis and return the new count."""
    r = _get_redis()
    try:
        key = _FAILED_LOGIN_KEY.format(player_id=player_id)
        count = await r.incr(key)
        # Set TTL on first failure (or reset it on subsequent failures)
        await r.expire(key, _FAILED_LOGIN_TTL)
        return count
    finally:
        await r.aclose()


async def _reset_failed_logins(player_id: UUID) -> None:
    """Reset the failed login counter on successful authentication."""
    r = _get_redis()
    try:
        key = _FAILED_LOGIN_KEY.format(player_id=player_id)
        await r.delete(key)
    finally:
        await r.aclose()


async def authenticate(
    session: AsyncSession,
    email: str,
    password: str,
    ip_address: str | None = None,
) -> TokenPair:
    """Authenticate a player and issue JWT tokens.

    Validates credentials, checks account lock status, and issues a
    JWT access + refresh token pair on success. Tracks failed attempts
    in Redis and locks the account after 3 consecutive failures.

    Args:
        session: Async database session.
        email: Player's email address.
        password: Plain-text password to verify.

    Returns:
        A TokenPair with access and refresh tokens.

    Raises:
        ValueError: If credentials are invalid.
        AccountLockedError: If the account is locked due to failed attempts.
    """
    # Look up the player by email
    result = await session.execute(
        select(Player).where(Player.email == email)
    )
    player = result.scalar_one_or_none()

    if player is None:
        raise ValueError("Invalid email or password")

    # Check if account is locked
    if await check_account_lock(player.id):
        raise AccountLockedError()

    # Verify password
    if not _verify_password(password, player.password_hash):
        # Audit: failed authentication
        from app.services.audit_service import create_audit_entry
        from app.models.audit import AuditEventType

        await create_audit_entry(
            session,
            event_type=AuditEventType.AUTH_FAILED,
            actor_id=player.id,
            details={"reason": "invalid_password"},
            ip_address=ip_address,
        )

        count = await _increment_failed_logins(player.id)
        if count >= _MAX_FAILED_ATTEMPTS:
            from app.tasks.email_tasks import send_notification_email
            send_notification_email.delay(str(player.id), "account_locked", player.email)
            raise AccountLockedError()
        raise ValueError("Invalid email or password")

    # Successful login — reset failed attempts
    await _reset_failed_logins(player.id)

    # Audit: successful authentication
    from app.services.audit_service import create_audit_entry
    from app.models.audit import AuditEventType

    await create_audit_entry(
        session,
        event_type=AuditEventType.AUTH_LOGIN,
        actor_id=player.id,
        details={"method": "email_password"},
        ip_address=ip_address,
    )

    return _issue_token_pair(player.id)


async def refresh_token(token: str) -> TokenPair:
    """Issue a new token pair from a valid refresh token.

    Args:
        token: A valid JWT refresh token.

    Returns:
        A new TokenPair with fresh access and refresh tokens.

    Raises:
        ValueError: If the token is invalid, expired, or not a refresh token.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as e:
        raise ValueError(f"Invalid refresh token: {e}")

    if payload.get("type") != "refresh":
        raise ValueError("Token is not a refresh token")

    player_id = UUID(payload["sub"])
    return _issue_token_pair(player_id)


async def request_password_reset(session: AsyncSession, email: str) -> None:
    """Generate a time-limited password reset token and send it via email.

    If the email doesn't match any account, this silently returns to avoid
    leaking account existence information.

    Args:
        session: Async database session.
        email: The email address to send the reset link to.
    """
    result = await session.execute(
        select(Player).where(Player.email == email)
    )
    player = result.scalar_one_or_none()

    if player is None:
        # Don't reveal whether the email exists
        return

    # Generate a reset token (JWT with short expiry)
    reset_token = _create_token(
        player.id,
        "password_reset",
        timedelta(hours=1),
    )

    from app.tasks.email_tasks import send_password_reset_email
    send_password_reset_email.delay(str(player.id), player.email, reset_token)


async def reset_password(
    session: AsyncSession,
    token: str,
    new_password: str,
) -> None:
    """Validate a reset token and update the player's password.

    Args:
        session: Async database session.
        token: The password reset JWT token.
        new_password: The new plain-text password (will be hashed).

    Raises:
        ValueError: If the token is invalid, expired, or not a reset token.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as e:
        raise ValueError(f"Invalid reset token: {e}")

    if payload.get("type") != "password_reset":
        raise ValueError("Token is not a password reset token")

    player_id = UUID(payload["sub"])

    result = await session.execute(
        select(Player).where(Player.id == player_id)
    )
    player = result.scalar_one_or_none()

    if player is None:
        raise ValueError("Player not found")

    player.password_hash = _hash_password(new_password)
    await session.flush()
