"""Leaderboard API endpoints.

Routes:
- GET /api/v1/leaderboard/{metric}     — get leaderboard for a metric
- GET /api/v1/leaderboard/{metric}/me  — get current player's rank

Requirements: 8.3, 8.4, 8.5
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_player_id, get_db
from app.models.player import Player
from app.schemas.leaderboard import LeaderboardEntry, LeaderboardResponse, PlayerRankResponse
from app.services import leaderboard_service
from app.services.leaderboard_service import VALID_METRICS, VALID_PERIODS

router = APIRouter(prefix="/api/v1/leaderboard", tags=["leaderboard"])


@router.get("/{metric}", response_model=LeaderboardResponse)
async def get_leaderboard(
    metric: str,
    period: str = Query("all_time", description="Time period: daily, weekly, monthly, all_time"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=100),
):
    """Return the leaderboard for a given metric and period.

    Requirement 8.3: Top 100 players with rank, username, metric value.
    Requirement 8.5: Daily, weekly, monthly, all-time views.
    """
    if metric not in VALID_METRICS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric '{metric}'. Must be one of: {', '.join(VALID_METRICS)}",
        )
    if period not in VALID_PERIODS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period '{period}'. Must be one of: {', '.join(VALID_PERIODS)}",
        )

    result = await leaderboard_service.get_leaderboard(
        metric=metric, period=period, page=page, page_size=page_size,
    )

    return LeaderboardResponse(
        metric=metric,
        period=period,
        entries=[
            LeaderboardEntry(rank=e.rank, username=e.username, value=e.value)
            for e in result["entries"]
        ],
        page=result["page"],
        page_size=result["page_size"],
        total=result["total"],
    )


@router.get("/{metric}/me", response_model=PlayerRankResponse)
async def get_my_rank(
    metric: str,
    period: str = Query("all_time", description="Time period: daily, weekly, monthly, all_time"),
    db: AsyncSession = Depends(get_db),
    player_id: UUID = Depends(get_current_player_id),
):
    """Return the current player's rank for a given metric and period.

    Requirement 8.4: Highlight viewing player's own rank and position.
    """
    if metric not in VALID_METRICS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric '{metric}'. Must be one of: {', '.join(VALID_METRICS)}",
        )
    if period not in VALID_PERIODS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period '{period}'. Must be one of: {', '.join(VALID_PERIODS)}",
        )

    # Fetch player username
    result = await db.execute(select(Player.username).where(Player.id == player_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Player not found")
    username = row

    rank = await leaderboard_service.get_player_rank(
        player_id=player_id, username=username, metric=metric, period=period,
    )

    return PlayerRankResponse(
        metric=metric,
        period=period,
        rank=rank.rank,
        value=rank.value,
        username=rank.username,
    )
