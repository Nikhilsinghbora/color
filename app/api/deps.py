"""Dependency injection for database sessions and JWT authentication."""

import time
from typing import AsyncGenerator
from uuid import UUID

from fastapi import Header, HTTPException
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.base import async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session, rolling back on error."""
    async with async_session_factory() as session:
        async with session.begin():
            yield session


async def get_current_player_id(
    authorization: str = Header(...),
) -> UUID:
    """Extract and validate player_id from a JWT Bearer token.

    Expects an Authorization header in the form 'Bearer <token>'.
    Decodes the JWT, verifies it is an access token, and returns
    the player_id from the 'sub' claim.
    """
    credentials_exception = HTTPException(
        status_code=401,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Extract Bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise credentials_exception

    token = parts[1]

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        raise credentials_exception

    # Must be an access token
    if payload.get("type") != "access":
        raise credentials_exception

    # Extract player_id from sub claim
    sub = payload.get("sub")
    if sub is None:
        raise credentials_exception

    try:
        return UUID(sub)
    except (ValueError, AttributeError):
        raise credentials_exception


# Maximum age (in seconds) for JWT issuance before re-authentication is required
_RECENT_AUTH_MAX_AGE = 10 * 60  # 10 minutes


async def require_recent_auth(
    authorization: str = Header(...),
) -> UUID:
    """Require that the JWT was issued within the last 10 minutes.

    This dependency is used for sensitive endpoints (wallet, account management).
    If the token's ``iat`` claim is older than 10 minutes, the request is
    rejected with a 401 asking the player to re-authenticate.

    Requirement 12.4: Re-authentication for wallet access.
    """
    credentials_exception = HTTPException(
        status_code=401,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise credentials_exception

    token = parts[1]

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        raise credentials_exception

    if payload.get("type") != "access":
        raise credentials_exception

    sub = payload.get("sub")
    if sub is None:
        raise credentials_exception

    # Check iat claim freshness
    iat = payload.get("iat")
    if iat is None:
        raise HTTPException(
            status_code=401,
            detail="Re-authentication required for wallet access",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if time.time() - iat > _RECENT_AUTH_MAX_AGE:
        raise HTTPException(
            status_code=401,
            detail="Re-authentication required for wallet access",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return UUID(sub)
    except (ValueError, AttributeError):
        raise credentials_exception
