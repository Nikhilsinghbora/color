"""Social service — invite codes, friend management, and profile display.

Provides:
- Unique invite code generation for private game rounds
- Friend add/remove by username
- Public profile statistics (total games, win rate, leaderboard rank)

Requirements: 9.1, 9.2, 9.4, 9.5
"""

import logging
import secrets
import string
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Bet, GameMode, GameRound, RoundPhase
from app.models.player import Player
from app.models.social import FriendLink
from app.services import leaderboard_service

logger = logging.getLogger(__name__)

_INVITE_CODE_LENGTH = 8
_INVITE_CODE_ALPHABET = string.ascii_uppercase + string.digits


def _generate_invite_code() -> str:
    """Generate a cryptographically random invite code.

    Uses ``secrets.choice`` to produce an 8-character alphanumeric code.
    The code space (36^8 ≈ 2.8 trillion) makes collisions extremely unlikely.
    """
    return "".join(
        secrets.choice(_INVITE_CODE_ALPHABET) for _ in range(_INVITE_CODE_LENGTH)
    )


@dataclass
class ProfileStats:
    username: str
    total_games_played: int
    win_rate: Decimal
    leaderboard_rank: Optional[int]
    member_since: datetime


async def create_private_round(
    session: AsyncSession,
    player_id: UUID,
    game_mode_id: UUID,
) -> tuple[GameRound, str]:
    """Create a private game round with a unique invite code.

    Generates a unique invite code and attaches it to a new game round in
    BETTING phase. Retries code generation on the (extremely unlikely)
    collision.

    Requirement 9.1: Generate unique invite code for private rounds.

    Returns:
        Tuple of (GameRound, invite_code).
    """
    from datetime import datetime, timedelta, timezone

    # Fetch game mode for round duration
    mode_result = await session.execute(
        select(GameMode).where(GameMode.id == game_mode_id)
    )
    game_mode = mode_result.scalar_one_or_none()
    if game_mode is None:
        raise ValueError(f"Game mode {game_mode_id} not found")

    now = datetime.now(timezone.utc)
    betting_ends_at = now + timedelta(seconds=game_mode.round_duration_seconds)

    # Retry loop for invite code uniqueness
    max_attempts = 5
    for _ in range(max_attempts):
        invite_code = _generate_invite_code()

        # Check uniqueness
        existing = await session.execute(
            select(GameRound.id).where(GameRound.invite_code == invite_code)
        )
        if existing.scalar_one_or_none() is not None:
            continue

        game_round = GameRound(
            game_mode_id=game_mode_id,
            phase=RoundPhase.BETTING,
            betting_ends_at=betting_ends_at,
            invite_code=invite_code,
            created_by=player_id,
        )
        session.add(game_round)
        try:
            await session.flush()
            return game_round, invite_code
        except IntegrityError:
            await session.rollback()
            continue

    raise RuntimeError("Failed to generate unique invite code after multiple attempts")


async def join_private_round(
    session: AsyncSession,
    player_id: UUID,
    invite_code: str,
) -> GameRound:
    """Join a private game round using an invite code.

    Requirement 9.2: Join private round via invite code.

    Returns:
        The GameRound that was joined.

    Raises:
        ValueError: If invite code is invalid or round is not in BETTING phase.
    """
    result = await session.execute(
        select(GameRound).where(GameRound.invite_code == invite_code)
    )
    game_round = result.scalar_one_or_none()

    if game_round is None:
        raise ValueError("Invalid invite code")

    if game_round.phase != RoundPhase.BETTING:
        raise ValueError("This round is no longer accepting players")

    return game_round


async def add_friend(
    session: AsyncSession,
    player_id: UUID,
    friend_username: str,
) -> FriendLink:
    """Add a friend by username.

    Creates a bidirectional friend link. If the link already exists,
    raises ValueError.

    Requirement 9.4: Add friends by username.

    Returns:
        The created FriendLink.

    Raises:
        ValueError: If username not found, is self, or already friends.
    """
    # Look up friend by username
    result = await session.execute(
        select(Player).where(Player.username == friend_username)
    )
    friend = result.scalar_one_or_none()

    if friend is None:
        raise ValueError(f"Player '{friend_username}' not found")

    if friend.id == player_id:
        raise ValueError("Cannot add yourself as a friend")

    # Check if already friends
    existing = await session.execute(
        select(FriendLink).where(
            FriendLink.player_id == player_id,
            FriendLink.friend_id == friend.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Already friends with '{friend_username}'")

    # Create bidirectional links
    link = FriendLink(player_id=player_id, friend_id=friend.id)
    reverse_link = FriendLink(player_id=friend.id, friend_id=player_id)
    session.add(link)
    session.add(reverse_link)

    try:
        await session.flush()
    except IntegrityError:
        raise ValueError(f"Already friends with '{friend_username}'")

    return link


async def get_friends(
    session: AsyncSession,
    player_id: UUID,
) -> list[dict]:
    """Return the player's friends list with usernames.

    Requirement 9.4: Friend list management.

    Returns:
        List of dicts with friend_id and username.
    """
    result = await session.execute(
        select(FriendLink.friend_id, Player.username)
        .join(Player, Player.id == FriendLink.friend_id)
        .where(FriendLink.player_id == player_id)
        .order_by(Player.username)
    )
    return [
        {"friend_id": str(row[0]), "username": row[1]}
        for row in result.all()
    ]


async def get_profile(
    session: AsyncSession,
    username: str,
) -> ProfileStats:
    """Return public profile statistics for a player.

    Computes total games played, win rate, and fetches leaderboard rank
    from Redis.

    Requirement 9.5: Display friend public statistics.

    Returns:
        ProfileStats with computed statistics.

    Raises:
        ValueError: If username not found.
    """
    # Fetch player
    result = await session.execute(
        select(Player).where(Player.username == username)
    )
    player = result.scalar_one_or_none()

    if player is None:
        raise ValueError(f"Player '{username}' not found")

    # Compute total games played (distinct rounds with resolved bets)
    games_result = await session.execute(
        select(func.count(func.distinct(Bet.round_id)))
        .where(Bet.player_id == player.id)
        .where(Bet.is_winner.isnot(None))
    )
    total_games = games_result.scalar() or 0

    # Compute win rate
    if total_games > 0:
        wins_result = await session.execute(
            select(func.count(func.distinct(Bet.round_id)))
            .where(Bet.player_id == player.id)
            .where(Bet.is_winner == True)  # noqa: E712
        )
        total_wins = wins_result.scalar() or 0
        win_rate = Decimal(str(total_wins)) / Decimal(str(total_games))
        win_rate = win_rate.quantize(Decimal("0.01"))
    else:
        win_rate = Decimal("0.00")

    # Fetch leaderboard rank (total_winnings, all_time)
    try:
        rank_info = await leaderboard_service.get_player_rank(
            player_id=player.id,
            username=player.username,
            metric="total_winnings",
            period="all_time",
        )
        leaderboard_rank = rank_info.rank
    except Exception:
        leaderboard_rank = None

    return ProfileStats(
        username=player.username,
        total_games_played=total_games,
        win_rate=win_rate,
        leaderboard_rank=leaderboard_rank,
        member_since=player.created_at,
    )
