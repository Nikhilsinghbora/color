"""Period number generator service.

Generates formatted period numbers for game rounds in the format:
    YYYYMMDD + mode_prefix(3) + sequence(7, zero-padded)

Example: "20250429" + "100" + "0051058" = "20250429100051058"

The sequence counter is scoped per game mode per UTC date and uses
an atomic database operation (INSERT ... ON CONFLICT UPDATE) to safely
increment without race conditions.

Functions:
    format_period_number   – format components into a period number string
    parse_period_number    – parse a period number back into components
    generate_period_number – atomically generate the next period number
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import PeriodSequence

logger = logging.getLogger(__name__)

MAX_SEQUENCE = 9999999
"""Maximum sequence value before overflow."""


def format_period_number(date_str: str, mode_prefix: str, sequence: int) -> str:
    """Format components into a period number string.

    Args:
        date_str: Date in YYYYMMDD format (8 characters).
        mode_prefix: Game mode prefix (3 characters).
        sequence: Sequence number (1–9999999).

    Returns:
        Formatted period number string of 18 characters.

    Raises:
        ValueError: If any component has an invalid length or value.
    """
    if len(date_str) != 8 or not date_str.isdigit():
        raise ValueError(f"date_str must be 8 digits, got '{date_str}'")
    if len(mode_prefix) != 3 or not mode_prefix.isdigit():
        raise ValueError(f"mode_prefix must be 3 digits, got '{mode_prefix}'")
    if sequence < 0 or sequence > MAX_SEQUENCE:
        raise ValueError(f"sequence must be 0–{MAX_SEQUENCE}, got {sequence}")

    return f"{date_str}{mode_prefix}{sequence:07d}"


def parse_period_number(period_number: str) -> tuple[str, str, int]:
    """Parse a period number string back into its components.

    Args:
        period_number: Formatted period number (18 characters).

    Returns:
        Tuple of (date_str, mode_prefix, sequence).

    Raises:
        ValueError: If the period number has an invalid format.
    """
    if len(period_number) != 18 or not period_number.isdigit():
        raise ValueError(
            f"period_number must be 18 digits, got '{period_number}' (len={len(period_number)})"
        )

    date_str = period_number[:8]
    mode_prefix = period_number[8:11]
    sequence = int(period_number[11:])

    return date_str, mode_prefix, sequence


async def generate_period_number(
    session: AsyncSession,
    game_mode_id: UUID,
    mode_prefix: str,
) -> str:
    """Atomically generate the next period number for a game mode and date.

    Uses INSERT ... ON CONFLICT UPDATE to safely increment the sequence
    counter without race conditions. If the sequence overflows past
    MAX_SEQUENCE, logs an error and continues with the next number.

    Args:
        session: Async database session.
        game_mode_id: The game mode UUID.
        mode_prefix: The 3-digit mode prefix string.

    Returns:
        Formatted period number string.
    """
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")

    # Atomic upsert: INSERT new row with last_sequence=1, or increment existing
    stmt = sqlite_insert(PeriodSequence).values(
        game_mode_id=game_mode_id,
        date_str=date_str,
        last_sequence=1,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["game_mode_id", "date_str"],
        set_={"last_sequence": PeriodSequence.last_sequence + 1},
    )
    await session.execute(stmt)

    # Read back the current sequence value
    result = await session.execute(
        select(PeriodSequence.last_sequence).where(
            PeriodSequence.game_mode_id == game_mode_id,
            PeriodSequence.date_str == date_str,
        )
    )
    sequence = result.scalar_one()

    # Handle overflow
    if sequence > MAX_SEQUENCE:
        logger.error(
            "Period sequence overflow for mode_prefix=%s date=%s: sequence=%d exceeds max=%d",
            mode_prefix,
            date_str,
            sequence,
            MAX_SEQUENCE,
        )

    return format_period_number(date_str, mode_prefix, sequence)
