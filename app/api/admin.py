"""Admin API endpoints.

Routes:
- GET  /api/v1/admin/dashboard                    — dashboard metrics
- PUT  /api/v1/admin/game-config/{mode_id}        — update game mode config
- POST /api/v1/admin/players/{player_id}/suspend   — suspend a player
- POST /api/v1/admin/players/{player_id}/ban       — ban a player
- GET  /api/v1/admin/audit-logs                    — paginated audit trail
- GET  /api/v1/admin/rng-audit                     — RNG audit log

All endpoints require the requesting player to have is_admin=True.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_player_id, get_db
from app.models.player import Player
from app.schemas.admin import (
    DashboardResponse,
    GameConfigUpdateRequest,
    PlayerActionRequest,
    ProfitSettingsRequest,
    ProfitSettingsResponse,
    ProfitGraphResponse,
    RoundProfitDetailsResponse,
)
from app.models.game import GameRound
from app.services import admin_service, profit_service

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


async def _require_admin(
    db: AsyncSession = Depends(get_db),
    player_id: UUID = Depends(get_current_player_id),
) -> UUID:
    """Verify the requesting player has admin privileges."""
    result = await db.execute(select(Player).where(Player.id == player_id))
    player = result.scalar_one_or_none()
    if player is None or not player.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return player_id


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    period_start: Optional[datetime] = Query(None),
    period_end: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    admin_id: UUID = Depends(_require_admin),
):
    """Return dashboard metrics for the given time period."""
    metrics = await admin_service.get_dashboard_metrics(
        db, period_start=period_start, period_end=period_end,
    )
    return DashboardResponse(**metrics)


@router.put("/game-config/{mode_id}")
async def update_game_config(
    mode_id: UUID,
    body: GameConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin_id: UUID = Depends(_require_admin),
):
    """Update game mode configuration. Changes apply from the next round."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        game_mode = await admin_service.update_game_config(
            db, mode_id=mode_id, admin_id=admin_id, updates=updates,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        "id": str(game_mode.id),
        "name": game_mode.name,
        "message": "Configuration updated. Changes apply from the next round.",
    }


@router.post("/players/{player_id}/suspend")
async def suspend_player(
    player_id: UUID,
    body: PlayerActionRequest,
    db: AsyncSession = Depends(get_db),
    admin_id: UUID = Depends(_require_admin),
):
    """Suspend a player account with a recorded reason."""
    try:
        player = await admin_service.suspend_player(
            db, player_id=player_id, admin_id=admin_id, reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        "id": str(player.id),
        "username": player.username,
        "is_active": player.is_active,
        "action": "suspended",
    }


@router.post("/players/{player_id}/ban")
async def ban_player(
    player_id: UUID,
    body: PlayerActionRequest,
    db: AsyncSession = Depends(get_db),
    admin_id: UUID = Depends(_require_admin),
):
    """Ban a player account with a recorded reason."""
    try:
        player = await admin_service.ban_player(
            db, player_id=player_id, admin_id=admin_id, reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        "id": str(player.id),
        "username": player.username,
        "is_active": player.is_active,
        "action": "banned",
    }


@router.get("/audit-logs")
async def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    event_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    admin_id: UUID = Depends(_require_admin),
):
    """Return paginated audit trail entries."""
    result = await admin_service.get_audit_logs(
        db, page=page, page_size=page_size, event_type=event_type,
    )
    return {
        "logs": [
            {
                "id": str(log.id),
                "event_type": log.event_type.value if hasattr(log.event_type, "value") else log.event_type,
                "actor_id": str(log.actor_id),
                "target_id": str(log.target_id) if log.target_id else None,
                "details": log.details,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in result["logs"]
        ],
        "page": result["page"],
        "page_size": result["page_size"],
        "total": result["total"],
    }


@router.get("/rng-audit")
async def get_rng_audit(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    admin_id: UUID = Depends(_require_admin),
):
    """Return paginated RNG audit log entries for fairness verification."""
    result = await admin_service.get_rng_audit_logs(
        db, page=page, page_size=page_size,
    )
    return {
        "logs": [
            {
                "id": str(log.id),
                "round_id": str(log.round_id),
                "algorithm": log.algorithm,
                "raw_value": log.raw_value,
                "num_options": log.num_options,
                "selected_color": log.selected_color,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in result["logs"]
        ],
        "page": result["page"],
        "page_size": result["page_size"],
        "total": result["total"],
    }


@router.get("/profit-settings", response_model=ProfitSettingsResponse)
async def get_profit_settings(
    db: AsyncSession = Depends(get_db),
    admin_id: UUID = Depends(_require_admin),
):
    """Get the currently active profit settings."""
    settings = await profit_service.get_active_profit_settings(db)
    if not settings:
        raise HTTPException(
            status_code=404,
            detail="No profit settings configured. Use POST to create initial settings."
        )
    return ProfitSettingsResponse.model_validate(settings)


@router.post("/profit-settings", response_model=ProfitSettingsResponse, status_code=201)
async def create_profit_settings(
    body: ProfitSettingsRequest,
    db: AsyncSession = Depends(get_db),
    admin_id: UUID = Depends(_require_admin),
):
    """Create or update profit settings (house profit vs winner pool).

    Example:
    - house_profit_percentage: 20
    - winners_pool_percentage: 80

    This means 20% of total bets goes to house, 80% available for winners.
    If calculated payouts exceed 80%, winners get reduced payouts.
    """
    try:
        settings = await profit_service.create_profit_settings(
            db,
            house_profit_percentage=body.house_profit_percentage,
            winners_pool_percentage=body.winners_pool_percentage,
        )
        await db.commit()
        return ProfitSettingsResponse.model_validate(settings)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/rounds/{round_id}/profit-details", response_model=RoundProfitDetailsResponse)
async def get_round_profit_details(
    round_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin_id: UUID = Depends(_require_admin),
):
    """Get detailed profit breakdown for a specific round."""
    result = await db.execute(
        select(GameRound).where(GameRound.id == round_id)
    )
    game_round = result.scalar_one_or_none()
    if not game_round:
        raise HTTPException(status_code=404, detail="Round not found")

    return RoundProfitDetailsResponse(
        round_id=game_round.id,
        total_bets=game_round.total_bets,
        total_payout_pool=game_round.total_payout_pool,
        house_profit=game_round.house_profit,
        total_calculated_payouts=game_round.total_calculated_payouts,
        total_actual_payouts=game_round.total_payouts,
        payout_reduced=game_round.payout_reduced,
        applied_house_percentage=game_round.applied_house_percentage,
        applied_winners_percentage=game_round.applied_winners_percentage,
        flagged_for_review=game_round.flagged_for_review,
    )


@router.get("/profit-graph", response_model=ProfitGraphResponse)
async def get_profit_graph(
    period: str = Query("daily", regex="^(daily|weekly|monthly)$"),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    admin_id: UUID = Depends(_require_admin),
):
    """Return aggregated profit & margin data for graphing.

    Query params:
    - period: "daily" | "weekly" | "monthly"
    - days: how many days of history (1–365, default 30)
    """
    data = await admin_service.get_profit_graph_data(
        db, period=period, days=days,
    )
    return ProfitGraphResponse(**data)
