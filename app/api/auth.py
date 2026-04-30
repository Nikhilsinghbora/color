"""Authentication API endpoints.

Routes:
- POST /api/v1/auth/register          — register a new player
- POST /api/v1/auth/login             — authenticate and get tokens
- POST /api/v1/auth/refresh           — refresh an access token
- POST /api/v1/auth/password-reset-request — request a password reset email
- POST /api/v1/auth/password-reset    — complete a password reset
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.exceptions import AccountLockedError
from app.schemas.auth import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new player and return tokens (auto-login)."""
    try:
        player = await auth_service.register_player(
            db,
            email=body.email,
            username=body.username,
            password=body.password,
        )
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="A player with this email or username already exists",
        )

    # Auto-login: issue tokens for the newly registered player
    token_pair = auth_service._issue_token_pair(player.id)
    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.expires_in,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate a player and return JWT tokens."""
    try:
        token_pair = await auth_service.authenticate(
            db,
            email=body.email,
            password=body.password,
        )
    except AccountLockedError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshTokenRequest):
    """Issue a new token pair from a valid refresh token."""
    try:
        token_pair = await auth_service.refresh_token(body.refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.expires_in,
    )


@router.post("/password-reset-request")
async def password_reset_request(
    body: PasswordResetRequest, db: AsyncSession = Depends(get_db)
):
    """Request a password reset email.

    Always returns success to avoid leaking account existence.
    """
    await auth_service.request_password_reset(db, email=body.email)
    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/password-reset")
async def password_reset(
    body: PasswordResetConfirm, db: AsyncSession = Depends(get_db)
):
    """Complete a password reset using a valid reset token."""
    try:
        await auth_service.reset_password(db, token=body.token, new_password=body.new_password)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    return {"message": "Password has been reset successfully"}
