"""Game mode service — CRUD operations for game mode configuration.

Supports Classic, Timed_Challenge, and Tournament mode types.
Each mode has independent color_options, odds, min_bet, max_bet,
and round_duration_seconds.
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import GameMode

VALID_MODE_TYPES = {"classic", "timed_challenge", "tournament"}


class InvalidModeTypeError(Exception):
    """Raised when an unsupported mode_type is provided."""

    def __init__(self, mode_type: str):
        self.mode_type = mode_type
        super().__init__(
            f"Invalid mode type '{mode_type}'. Must be one of: {', '.join(sorted(VALID_MODE_TYPES))}"
        )


class GameModeNotFoundError(Exception):
    """Raised when a game mode cannot be found."""

    def __init__(self, mode_id: UUID):
        self.mode_id = mode_id
        super().__init__(f"Game mode {mode_id} not found")


async def create_game_mode(
    session: AsyncSession,
    name: str,
    mode_type: str,
    color_options: list[str],
    odds: dict[str, float],
    min_bet: Decimal,
    max_bet: Decimal,
    round_duration_seconds: int,
) -> GameMode:
    """Create a new game mode.

    Args:
        session: Async database session.
        name: Display name for the game mode.
        mode_type: One of 'classic', 'timed_challenge', 'tournament'.
        color_options: List of available colors.
        odds: Mapping of color to odds multiplier.
        min_bet: Minimum bet amount.
        max_bet: Maximum bet amount.
        round_duration_seconds: Duration of the betting phase.

    Returns:
        The newly created GameMode.

    Raises:
        InvalidModeTypeError: If mode_type is not supported.
    """
    if mode_type not in VALID_MODE_TYPES:
        raise InvalidModeTypeError(mode_type)

    game_mode = GameMode(
        name=name,
        mode_type=mode_type,
        color_options=color_options,
        odds=odds,
        min_bet=min_bet,
        max_bet=max_bet,
        round_duration_seconds=round_duration_seconds,
    )
    session.add(game_mode)
    await session.flush()
    return game_mode


async def get_game_mode(session: AsyncSession, mode_id: UUID) -> GameMode:
    """Retrieve a game mode by ID.

    Args:
        session: Async database session.
        mode_id: The UUID of the game mode.

    Returns:
        The GameMode instance.

    Raises:
        GameModeNotFoundError: If no game mode exists with the given ID.
    """
    result = await session.execute(
        select(GameMode).where(GameMode.id == mode_id)
    )
    game_mode = result.scalar_one_or_none()
    if game_mode is None:
        raise GameModeNotFoundError(mode_id)
    return game_mode


async def list_game_modes(
    session: AsyncSession, active_only: bool = True
) -> list[GameMode]:
    """List game modes, optionally filtering to active only.

    Args:
        session: Async database session.
        active_only: If True, return only active game modes.

    Returns:
        List of GameMode instances.
    """
    stmt = select(GameMode)
    if active_only:
        stmt = stmt.where(GameMode.is_active == True)  # noqa: E712
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_game_mode(
    session: AsyncSession, mode_id: UUID, **kwargs
) -> GameMode:
    """Update a game mode's configuration.

    Supported fields: name, mode_type, color_options, odds,
    min_bet, max_bet, round_duration_seconds, is_active.

    Args:
        session: Async database session.
        mode_id: The UUID of the game mode to update.
        **kwargs: Fields to update.

    Returns:
        The updated GameMode instance.

    Raises:
        GameModeNotFoundError: If no game mode exists with the given ID.
        InvalidModeTypeError: If mode_type is provided and not supported.
    """
    game_mode = await get_game_mode(session, mode_id)

    if "mode_type" in kwargs and kwargs["mode_type"] not in VALID_MODE_TYPES:
        raise InvalidModeTypeError(kwargs["mode_type"])

    allowed_fields = {
        "name", "mode_type", "color_options", "odds",
        "min_bet", "max_bet", "round_duration_seconds", "is_active",
    }
    for key, value in kwargs.items():
        if key in allowed_fields:
            setattr(game_mode, key, value)

    await session.flush()
    return game_mode


async def delete_game_mode(session: AsyncSession, mode_id: UUID) -> None:
    """Soft-delete a game mode by setting is_active=False.

    Args:
        session: Async database session.
        mode_id: The UUID of the game mode to deactivate.

    Raises:
        GameModeNotFoundError: If no game mode exists with the given ID.
    """
    game_mode = await get_game_mode(session, mode_id)
    game_mode.is_active = False
    await session.flush()
