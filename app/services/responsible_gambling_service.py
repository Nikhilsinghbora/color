"""Responsible gambling service for deposit limits, session limits, loss thresholds, and self-exclusion.

Provides standalone async functions following the same pattern as wallet_service.py
and auth_service.py. Enforces daily/weekly/monthly deposit limits, session time limits,
cumulative loss threshold warnings, and self-exclusion periods.

Requirements: 10.1, 10.2, 10.3, 10.4, 10.6
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import NamedTuple, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DepositLimitExceededError, SelfExcludedError
from app.models.player import Transaction, TransactionType
from app.models.responsible_gambling import (
    DepositLimit,
    LimitPeriod,
    SelfExclusion,
    SessionLimit,
)

logger = logging.getLogger(__name__)

# Configurable loss threshold for 24h cumulative loss warning (Requirement 10.6)
DEFAULT_LOSS_THRESHOLD = Decimal("1000.00")

# Duration mappings for self-exclusion
_EXCLUSION_DURATIONS = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


def _ensure_aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (UTC). Handles naive datetimes from SQLite."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class LimitCheckResult(NamedTuple):
    """Result of a deposit limit check."""

    allowed: bool
    remaining: Decimal
    resets_at: Optional[datetime]
    period: Optional[str]


def _compute_reset_time(period: LimitPeriod, now: datetime) -> datetime:
    """Compute the next reset timestamp for a given limit period."""
    if period == LimitPeriod.DAILY:
        next_day = now + timedelta(days=1)
        return next_day.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == LimitPeriod.WEEKLY:
        days_until_monday = (7 - now.weekday()) % 7 or 7
        next_monday = now + timedelta(days=days_until_monday)
        return next_monday.replace(hour=0, minute=0, second=0, microsecond=0)
    else:  # MONTHLY
        if now.month == 12:
            return datetime(now.year + 1, 1, 1, tzinfo=now.tzinfo)
        return datetime(now.year, now.month + 1, 1, tzinfo=now.tzinfo)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def set_deposit_limit(
    session: AsyncSession,
    player_id: UUID,
    period: str,
    amount: Decimal,
) -> DepositLimit:
    """Set or update a daily/weekly/monthly deposit limit for a player.

    If a limit already exists for the given period, updates the amount.
    Resets current_usage to 0 and computes a new reset timestamp.

    Requirement 10.1: Allow player to set daily/weekly/monthly deposit limit.
    """
    limit_period = LimitPeriod(period)
    now = datetime.now(timezone.utc)
    resets_at = _compute_reset_time(limit_period, now)

    result = await session.execute(
        select(DepositLimit).where(
            DepositLimit.player_id == player_id,
            DepositLimit.period == limit_period,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.amount = amount
        existing.current_usage = Decimal("0.00")
        existing.resets_at = resets_at
        await session.flush()
        return existing

    deposit_limit = DepositLimit(
        player_id=player_id,
        period=limit_period,
        amount=amount,
        current_usage=Decimal("0.00"),
        resets_at=resets_at,
    )
    session.add(deposit_limit)
    await session.flush()
    return deposit_limit


async def check_deposit_limit(
    session: AsyncSession,
    player_id: UUID,
    amount: Decimal,
) -> LimitCheckResult:
    """Validate a deposit against all configured limits for a player.

    Checks daily, weekly, and monthly limits. If any limit would be exceeded,
    raises DepositLimitExceededError with remaining allowance and reset date.

    Requirement 10.2: Reject deposits exceeding limit with remaining allowance and reset date.
    """
    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(DepositLimit).where(DepositLimit.player_id == player_id)
    )
    limits = list(result.scalars().all())

    if not limits:
        return LimitCheckResult(
            allowed=True,
            remaining=Decimal("999999.99"),
            resets_at=None,
            period=None,
        )

    # Find the most restrictive limit that would be violated
    for limit in limits:
        # Auto-reset if the period has expired
        if now >= _ensure_aware(limit.resets_at):
            limit.current_usage = Decimal("0.00")
            limit.resets_at = _compute_reset_time(limit.period, now)

        remaining = limit.amount - limit.current_usage
        if amount > remaining:
            raise DepositLimitExceededError(
                limit=limit.amount,
                current_usage=limit.current_usage,
                requested=amount,
                resets_at=limit.resets_at,
            )

    # All limits pass — find the smallest remaining allowance
    min_remaining = min(
        limit.amount - limit.current_usage for limit in limits
    )
    tightest = min(limits, key=lambda l: l.amount - l.current_usage)

    return LimitCheckResult(
        allowed=True,
        remaining=min_remaining,
        resets_at=tightest.resets_at,
        period=tightest.period.value,
    )


async def record_deposit_usage(
    session: AsyncSession,
    player_id: UUID,
    amount: Decimal,
) -> None:
    """Record a deposit against all active limits for a player.

    Called after a successful deposit to increment current_usage.
    """
    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(DepositLimit).where(DepositLimit.player_id == player_id)
    )
    limits = list(result.scalars().all())

    for limit in limits:
        if now >= _ensure_aware(limit.resets_at):
            limit.current_usage = Decimal("0.00")
            limit.resets_at = _compute_reset_time(limit.period, now)
        limit.current_usage += amount

    await session.flush()


async def set_session_limit(
    session: AsyncSession,
    player_id: UUID,
    duration_minutes: int,
) -> None:
    """Set or update a session time limit for a player.

    After the configured duration, the platform displays a mandatory reminder.

    Requirement 10.3: Session time limit with mandatory reminder notification.
    """
    result = await session.execute(
        select(SessionLimit).where(SessionLimit.player_id == player_id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.duration_minutes = duration_minutes
        await session.flush()
        return

    session_limit = SessionLimit(
        player_id=player_id,
        duration_minutes=duration_minutes,
    )
    session.add(session_limit)
    await session.flush()


async def get_session_limit(
    session: AsyncSession,
    player_id: UUID,
) -> Optional[SessionLimit]:
    """Return the current session limit for a player, or None if not set."""
    result = await session.execute(
        select(SessionLimit).where(SessionLimit.player_id == player_id)
    )
    return result.scalar_one_or_none()


async def check_loss_threshold(
    session: AsyncSession,
    player_id: UUID,
    threshold: Optional[Decimal] = None,
) -> bool:
    """Check if a player's 24h cumulative losses exceed the configurable threshold.

    Losses are calculated as sum(bet_debits) - sum(payout_credits) over the last 24 hours.
    Returns True if losses exceed the threshold (warning should be triggered).

    Requirement 10.6: Mandatory warning when 24h cumulative losses exceed threshold.
    """
    if threshold is None:
        threshold = DEFAULT_LOSS_THRESHOLD

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=24)

    # Sum of bet debits in the last 24h
    from sqlalchemy import func

    debit_result = await session.execute(
        select(func.coalesce(func.sum(Transaction.amount), Decimal("0.00"))).where(
            Transaction.player_id == player_id,
            Transaction.type == TransactionType.BET_DEBIT,
            Transaction.created_at >= window_start,
        )
    )
    total_debits = debit_result.scalar_one()

    # Sum of payout credits in the last 24h
    credit_result = await session.execute(
        select(func.coalesce(func.sum(Transaction.amount), Decimal("0.00"))).where(
            Transaction.player_id == player_id,
            Transaction.type == TransactionType.PAYOUT_CREDIT,
            Transaction.created_at >= window_start,
        )
    )
    total_credits = credit_result.scalar_one()

    net_loss = total_debits - total_credits
    return net_loss > threshold


async def self_exclude(
    session: AsyncSession,
    player_id: UUID,
    duration: str,
) -> None:
    """Suspend a player's account for the selected self-exclusion duration.

    Supported durations: 24h, 7d, 30d, permanent.
    Prevents re-activation before the exclusion period ends.

    Requirement 10.4: Immediate suspension, prevent re-activation before period ends.
    """
    now = datetime.now(timezone.utc)

    # Check for existing active exclusion
    result = await session.execute(
        select(SelfExclusion).where(
            SelfExclusion.player_id == player_id,
            SelfExclusion.is_active == True,  # noqa: E712
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        # If permanent or not yet expired, prevent re-activation
        if existing.ends_at is None or now < _ensure_aware(existing.ends_at):
            raise SelfExcludedError(ends_at=existing.ends_at)

        # Previous exclusion has expired — deactivate it
        existing.is_active = False

    # Compute end time
    if duration == "permanent":
        ends_at = None
    else:
        delta = _EXCLUSION_DURATIONS.get(duration)
        if delta is None:
            raise ValueError(f"Invalid exclusion duration: {duration}")
        ends_at = now + delta

    exclusion = SelfExclusion(
        player_id=player_id,
        duration=duration,
        starts_at=now,
        ends_at=ends_at,
        is_active=True,
    )
    session.add(exclusion)
    await session.flush()


async def check_self_exclusion(
    session: AsyncSession,
    player_id: UUID,
) -> None:
    """Check if a player is currently self-excluded. Raises SelfExcludedError if so.

    Auto-deactivates expired exclusions.
    """
    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(SelfExclusion).where(
            SelfExclusion.player_id == player_id,
            SelfExclusion.is_active == True,  # noqa: E712
        )
    )
    exclusion = result.scalar_one_or_none()

    if exclusion is None:
        return

    # Permanent exclusion — always active
    if exclusion.ends_at is None:
        raise SelfExcludedError(ends_at=None)

    # Check if exclusion has expired
    if now >= _ensure_aware(exclusion.ends_at):
        exclusion.is_active = False
        await session.flush()
        return

    raise SelfExcludedError(ends_at=exclusion.ends_at)


async def get_deposit_limits(
    session: AsyncSession,
    player_id: UUID,
) -> list[DepositLimit]:
    """Return all deposit limits for a player."""
    result = await session.execute(
        select(DepositLimit).where(DepositLimit.player_id == player_id)
    )
    return list(result.scalars().all())
