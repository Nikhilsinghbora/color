"""Responsible gambling API endpoints.

Routes:
- POST /api/v1/responsible-gambling/deposit-limit   — set a deposit limit
- GET  /api/v1/responsible-gambling/deposit-limit   — get current deposit limits
- POST /api/v1/responsible-gambling/session-limit   — set a session time limit
- POST /api/v1/responsible-gambling/self-exclude    — request self-exclusion

Requirements: 10.1, 10.3, 10.4
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_player_id, get_db
from app.schemas.responsible_gambling import (
    DepositLimitRequest,
    DepositLimitResponse,
    SelfExclusionRequest,
    SessionLimitRequest,
)
from app.services import responsible_gambling_service

router = APIRouter(prefix="/api/v1/responsible-gambling", tags=["responsible-gambling"])


@router.post("/deposit-limit", response_model=DepositLimitResponse, status_code=200)
async def set_deposit_limit(
    body: DepositLimitRequest,
    db: AsyncSession = Depends(get_db),
    player_id: UUID = Depends(get_current_player_id),
):
    """Set or update a daily/weekly/monthly deposit limit for the authenticated player."""
    limit = await responsible_gambling_service.set_deposit_limit(
        db,
        player_id=player_id,
        period=body.period,
        amount=body.amount,
    )
    remaining = limit.amount - limit.current_usage
    return DepositLimitResponse(
        period=limit.period.value,
        amount=limit.amount,
        current_usage=limit.current_usage,
        remaining=remaining,
        resets_at=limit.resets_at,
    )


@router.get("/deposit-limit", response_model=list[DepositLimitResponse])
async def get_deposit_limits(
    db: AsyncSession = Depends(get_db),
    player_id: UUID = Depends(get_current_player_id),
):
    """Return all deposit limits for the authenticated player."""
    limits = await responsible_gambling_service.get_deposit_limits(db, player_id)
    return [
        DepositLimitResponse(
            period=limit.period.value,
            amount=limit.amount,
            current_usage=limit.current_usage,
            remaining=limit.amount - limit.current_usage,
            resets_at=limit.resets_at,
        )
        for limit in limits
    ]


@router.post("/session-limit", status_code=200)
async def set_session_limit(
    body: SessionLimitRequest,
    db: AsyncSession = Depends(get_db),
    player_id: UUID = Depends(get_current_player_id),
):
    """Set or update a session time limit for the authenticated player."""
    await responsible_gambling_service.set_session_limit(
        db,
        player_id=player_id,
        duration_minutes=body.duration_minutes,
    )
    return {"message": "Session limit set", "duration_minutes": body.duration_minutes}


@router.post("/self-exclude", status_code=200)
async def self_exclude(
    body: SelfExclusionRequest,
    db: AsyncSession = Depends(get_db),
    player_id: UUID = Depends(get_current_player_id),
):
    """Request self-exclusion for the authenticated player.

    Immediately suspends the account for the selected duration.
    Raises SelfExcludedError (handled by middleware) if already excluded.
    """
    await responsible_gambling_service.self_exclude(
        db,
        player_id=player_id,
        duration=body.duration,
    )
    return {"message": f"Self-exclusion activated for {body.duration}"}
