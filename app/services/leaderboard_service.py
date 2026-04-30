"""Leaderboard service using Redis sorted sets.

Maintains ranked leaderboards by total_winnings, win_rate, and win_streak
across daily, weekly, monthly, and all-time periods. Rankings are stored
in Redis sorted sets keyed as ``leaderboard:{metric}:{period}``.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.game import Bet, GameRound, Payout, RoundPhase
from app.models.player import Player

logger = logging.getLogger(__name__)

VALID_METRICS = ("total_winnings", "win_rate", "win_streak")
VALID_PERIODS = ("daily", "weekly", "monthly", "all_time")

_MAX_LEADERBOARD_SIZE = 100


def _leaderboard_key(metric: str, period: str) -> str:
    """Return the Redis sorted-set key for a leaderboard."""
    return f"leaderboard:{metric}:{period}"


@dataclass
class LeaderboardEntry:
    rank: int
    username: str
    value: Decimal


@dataclass
class PlayerRank:
    rank: Optional[int]
    username: str
    value: Optional[Decimal]


async def _get_redis() -> Optional[aioredis.Redis]:
    """Return a Redis client, or None if unavailable."""
    try:
        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        return client
    except Exception:
        logger.warning("Redis unavailable for leaderboard operations")
        return None


# ---------------------------------------------------------------------------
# Period filter helpers
# ---------------------------------------------------------------------------

def _period_interval_sql(period: str) -> Optional[str]:
    """Return a SQL interval string for the given period, or None for all_time."""
    mapping = {
        "daily": "1 day",
        "weekly": "7 days",
        "monthly": "30 days",
    }
    return mapping.get(period)


# ---------------------------------------------------------------------------
# Ranking computation from DB
# ---------------------------------------------------------------------------

async def _compute_total_winnings(
    session: AsyncSession, period: str
) -> list[tuple[UUID, str, Decimal]]:
    """Compute total winnings per player for the given period.

    Returns list of (player_id, username, total_winnings) sorted descending.
    """
    query = (
        select(
            Player.id,
            Player.username,
            func.coalesce(func.sum(Payout.amount), Decimal("0.00")).label("total_winnings"),
        )
        .join(Payout, Payout.player_id == Player.id)
        .join(GameRound, GameRound.id == Payout.round_id)
        .where(Payout.credited == True)  # noqa: E712
    )

    interval = _period_interval_sql(period)
    if interval:
        query = query.where(
            Payout.created_at >= func.now() - text(f"interval '{interval}'")
        )

    query = (
        query.group_by(Player.id, Player.username)
        .order_by(text("total_winnings DESC"))
        .limit(_MAX_LEADERBOARD_SIZE)
    )

    result = await session.execute(query)
    return [(row[0], row[1], Decimal(str(row[2]))) for row in result.all()]


async def _compute_win_rate(
    session: AsyncSession, period: str
) -> list[tuple[UUID, str, Decimal]]:
    """Compute win rate per player for the given period.

    Win rate = wins / total_bets. Only players with at least 1 bet are included.
    Returns list of (player_id, username, win_rate) sorted descending.
    """
    query = (
        select(
            Player.id,
            Player.username,
            (
                func.cast(
                    func.sum(case((Bet.is_winner == True, 1), else_=0)),  # noqa: E712
                    Decimal,
                )
                / func.cast(func.count(Bet.id), Decimal)
            ).label("win_rate"),
        )
        .join(Bet, Bet.player_id == Player.id)
        .join(GameRound, GameRound.id == Bet.round_id)
        .where(Bet.is_winner.isnot(None))
    )

    interval = _period_interval_sql(period)
    if interval:
        query = query.where(
            Bet.created_at >= func.now() - text(f"interval '{interval}'")
        )

    query = (
        query.group_by(Player.id, Player.username)
        .order_by(text("win_rate DESC"))
        .limit(_MAX_LEADERBOARD_SIZE)
    )

    result = await session.execute(query)
    return [(row[0], row[1], Decimal(str(row[2]))) for row in result.all()]


async def _compute_win_streak(
    session: AsyncSession, period: str
) -> list[tuple[UUID, str, Decimal]]:
    """Compute longest win streak per player for the given period.

    Uses a simplified approach: counts the current consecutive wins from
    the most recent bet backwards. For a full historical longest streak,
    a more complex window query would be needed; this is sufficient for
    leaderboard ranking purposes.

    Returns list of (player_id, username, streak) sorted descending.
    """
    # Fetch all resolved bets ordered by player and time
    query = (
        select(Bet.player_id, Bet.is_winner, Bet.created_at)
        .join(GameRound, GameRound.id == Bet.round_id)
        .where(Bet.is_winner.isnot(None))
    )

    interval = _period_interval_sql(period)
    if interval:
        query = query.where(
            Bet.created_at >= func.now() - text(f"interval '{interval}'")
        )

    query = query.order_by(Bet.player_id, Bet.created_at.desc())
    result = await session.execute(query)
    rows = result.all()

    # Compute longest streak per player
    streaks: dict[UUID, int] = {}
    current_player: Optional[UUID] = None
    current_streak = 0
    max_streak = 0

    for player_id, is_winner, _ in rows:
        if player_id != current_player:
            if current_player is not None:
                streaks[current_player] = max(streaks.get(current_player, 0), max_streak)
            current_player = player_id
            current_streak = 0
            max_streak = 0

        if is_winner:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0

    if current_player is not None:
        streaks[current_player] = max(streaks.get(current_player, 0), max_streak)

    if not streaks:
        return []

    # Fetch usernames for players with streaks
    player_ids = list(streaks.keys())
    username_result = await session.execute(
        select(Player.id, Player.username).where(Player.id.in_(player_ids))
    )
    username_map = {row[0]: row[1] for row in username_result.all()}

    # Sort by streak descending, limit to top 100
    ranked = sorted(streaks.items(), key=lambda x: x[1], reverse=True)[:_MAX_LEADERBOARD_SIZE]
    return [
        (pid, username_map.get(pid, "unknown"), Decimal(str(streak)))
        for pid, streak in ranked
    ]


_METRIC_COMPUTERS = {
    "total_winnings": _compute_total_winnings,
    "win_rate": _compute_win_rate,
    "win_streak": _compute_win_streak,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def update_rankings(session: AsyncSession, round_id: UUID) -> None:
    """Recompute and store leaderboard rankings after a round completes.

    Called by the ``update_leaderboards`` Celery task within 10 seconds of
    round completion. Recomputes all metric/period combinations and writes
    them to Redis sorted sets.

    Requirement 8.2: Update within 10 seconds of round completion.
    """
    client = await _get_redis()
    if client is None:
        logger.error("Cannot update leaderboard rankings: Redis unavailable")
        return

    try:
        for metric in VALID_METRICS:
            computer = _METRIC_COMPUTERS[metric]
            for period in VALID_PERIODS:
                try:
                    rankings = await computer(session, period)
                    key = _leaderboard_key(metric, period)

                    # Clear and repopulate the sorted set atomically via pipeline
                    pipe = client.pipeline()
                    pipe.delete(key)
                    for player_id, username, value in rankings:
                        # Store as score=float(value), member="player_id:username"
                        member = f"{player_id}:{username}"
                        pipe.zadd(key, {member: float(value)})
                    await pipe.execute()

                    logger.info(
                        "Updated leaderboard %s/%s with %d entries",
                        metric, period, len(rankings),
                    )
                except Exception:
                    logger.exception(
                        "Failed to update leaderboard %s/%s", metric, period
                    )
    finally:
        await client.aclose()


async def get_leaderboard(
    metric: str,
    period: str,
    page: int = 1,
    page_size: int = 100,
) -> dict:
    """Return the leaderboard for a given metric and period.

    Returns a dict with keys: entries, metric, period, page, page_size, total.
    Entries are sorted descending by metric value.

    Requirement 8.3: Top 100 players with rank, username, metric value.
    Requirement 8.5: Daily, weekly, monthly, all-time views.
    """
    if metric not in VALID_METRICS:
        raise ValueError(f"Invalid metric: {metric}. Must be one of {VALID_METRICS}")
    if period not in VALID_PERIODS:
        raise ValueError(f"Invalid period: {period}. Must be one of {VALID_PERIODS}")

    client = await _get_redis()
    if client is None:
        return {
            "entries": [],
            "metric": metric,
            "period": period,
            "page": page,
            "page_size": page_size,
            "total": 0,
        }

    try:
        key = _leaderboard_key(metric, period)
        total = await client.zcard(key)

        # Redis ZREVRANGE returns highest scores first (descending)
        start = (page - 1) * page_size
        end = start + page_size - 1
        # Use zrevrange with scores
        raw = await client.zrevrange(key, start, end, withscores=True)

        entries = []
        for rank_offset, (member, score) in enumerate(raw):
            # member format: "player_id:username"
            parts = member.split(":", 1)
            username = parts[1] if len(parts) > 1 else parts[0]
            entries.append(
                LeaderboardEntry(
                    rank=start + rank_offset + 1,
                    username=username,
                    value=Decimal(str(score)),
                )
            )

        return {
            "entries": entries,
            "metric": metric,
            "period": period,
            "page": page,
            "page_size": page_size,
            "total": total,
        }
    finally:
        await client.aclose()


async def get_player_rank(
    player_id: UUID,
    username: str,
    metric: str,
    period: str,
) -> PlayerRank:
    """Return a specific player's rank and score for a metric/period.

    Requirement 8.4: Highlight viewing player's own rank and position.
    """
    if metric not in VALID_METRICS:
        raise ValueError(f"Invalid metric: {metric}. Must be one of {VALID_METRICS}")
    if period not in VALID_PERIODS:
        raise ValueError(f"Invalid period: {period}. Must be one of {VALID_PERIODS}")

    client = await _get_redis()
    if client is None:
        return PlayerRank(rank=None, username=username, value=None)

    try:
        key = _leaderboard_key(metric, period)
        member = f"{player_id}:{username}"

        # ZREVRANK returns 0-based rank (highest score = rank 0)
        rank_index = await client.zrevrank(key, member)
        if rank_index is None:
            return PlayerRank(rank=None, username=username, value=None)

        score = await client.zscore(key, member)
        return PlayerRank(
            rank=rank_index + 1,  # 1-based
            username=username,
            value=Decimal(str(score)) if score is not None else None,
        )
    finally:
        await client.aclose()
