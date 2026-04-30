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
)
from app.services import admin_service

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
