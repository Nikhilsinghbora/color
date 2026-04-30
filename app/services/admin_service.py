"""Admin service for dashboard metrics, config management, and player actions."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEventType, AuditTrail
from app.models.game import Bet, GameMode, Payout
from app.models.player import Player
from app.models.rng import RNGAuditLog


async def get_dashboard_metrics(
    session: AsyncSession,
    *,
    period_start: Optional[datetime] = None,
    period_end: Optional[datetime] = None,
) -> dict:
    """Return dashboard metrics for the given time period.

    Metrics: active player count, total bets, total payouts, platform revenue.
    Defaults to last 24 hours if no period specified.
    """
    now = datetime.now(timezone.utc)
    if period_end is None:
        period_end = now
    if period_start is None:
        period_start = period_end - timedelta(days=1)

    # Active players: distinct players who placed bets in the period
    active_q = select(func.count(func.distinct(Bet.player_id))).where(
        Bet.created_at >= period_start,
        Bet.created_at <= period_end,
    )
    active_result = await session.execute(active_q)
    active_players = active_result.scalar_one() or 0

    # Total bets amount
    bets_q = select(func.coalesce(func.sum(Bet.amount), Decimal("0.00"))).where(
        Bet.created_at >= period_start,
        Bet.created_at <= period_end,
    )
    bets_result = await session.execute(bets_q)
    total_bets = bets_result.scalar_one()

    # Total payouts amount
    payouts_q = select(func.coalesce(func.sum(Payout.amount), Decimal("0.00"))).where(
        Payout.created_at >= period_start,
        Payout.created_at <= period_end,
    )
    payouts_result = await session.execute(payouts_q)
    total_payouts = payouts_result.scalar_one()

    platform_revenue = total_bets - total_payouts

    return {
        "active_players": active_players,
        "total_bets": total_bets,
        "total_payouts": total_payouts,
        "platform_revenue": platform_revenue,
        "period_start": period_start,
        "period_end": period_end,
    }


async def update_game_config(
    session: AsyncSession,
    *,
    mode_id: UUID,
    admin_id: UUID,
    updates: dict,
) -> GameMode:
    """Update game mode configuration and log the change.

    Changes apply starting from the next game round.
    """
    result = await session.execute(select(GameMode).where(GameMode.id == mode_id))
    game_mode = result.scalar_one_or_none()
    if game_mode is None:
        raise ValueError(f"Game mode {mode_id} not found")

    old_values = {}
    for field, value in updates.items():
        if value is not None and hasattr(game_mode, field):
            old_values[field] = getattr(game_mode, field)
            setattr(game_mode, field, value)

    # Log the config change in audit trail
    from app.services.audit_service import create_audit_entry

    await create_audit_entry(
        session,
        event_type=AuditEventType.ADMIN_CONFIG_CHANGE,
        actor_id=admin_id,
        target_id=mode_id,
        details={
            "mode_id": str(mode_id),
            "old_values": {k: str(v) for k, v in old_values.items()},
            "new_values": {k: str(v) for k, v in updates.items() if v is not None},
        },
    )

    return game_mode


async def suspend_player(
    session: AsyncSession,
    *,
    player_id: UUID,
    admin_id: UUID,
    reason: str,
) -> Player:
    """Suspend a player account and log the action."""
    result = await session.execute(select(Player).where(Player.id == player_id))
    player = result.scalar_one_or_none()
    if player is None:
        raise ValueError(f"Player {player_id} not found")

    player.is_active = False

    from app.services.audit_service import create_audit_entry

    await create_audit_entry(
        session,
        event_type=AuditEventType.ADMIN_PLAYER_ACTION,
        actor_id=admin_id,
        target_id=player_id,
        details={"action": "suspend", "reason": reason},
    )

    return player


async def ban_player(
    session: AsyncSession,
    *,
    player_id: UUID,
    admin_id: UUID,
    reason: str,
) -> Player:
    """Ban a player account and log the action."""
    result = await session.execute(select(Player).where(Player.id == player_id))
    player = result.scalar_one_or_none()
    if player is None:
        raise ValueError(f"Player {player_id} not found")

    player.is_active = False

    from app.services.audit_service import create_audit_entry

    await create_audit_entry(
        session,
        event_type=AuditEventType.ADMIN_PLAYER_ACTION,
        actor_id=admin_id,
        target_id=player_id,
        details={"action": "ban", "reason": reason},
    )

    return player


async def get_audit_logs(
    session: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 50,
    event_type: Optional[str] = None,
) -> dict:
    """Return paginated audit trail entries, most recent first."""
    query = select(AuditTrail).order_by(AuditTrail.created_at.desc())

    if event_type is not None:
        query = query.where(AuditTrail.event_type == event_type)

    # Count total
    count_q = select(func.count(AuditTrail.id))
    if event_type is not None:
        count_q = count_q.where(AuditTrail.event_type == event_type)
    total_result = await session.execute(count_q)
    total = total_result.scalar_one()

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await session.execute(query)
    logs = result.scalars().all()

    return {"logs": logs, "page": page, "page_size": page_size, "total": total}


async def get_rng_audit_logs(
    session: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Return paginated RNG audit log entries for fairness verification."""
    count_q = select(func.count(RNGAuditLog.id))
    total_result = await session.execute(count_q)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    query = (
        select(RNGAuditLog)
        .order_by(RNGAuditLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(query)
    logs = result.scalars().all()

    return {"logs": logs, "page": page, "page_size": page_size, "total": total}
