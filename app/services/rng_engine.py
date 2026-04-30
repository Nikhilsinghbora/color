"""RNG engine service using Python's secrets module (CSPRNG).

Generates cryptographically secure random outcomes for game rounds and
records every result in an append-only audit log for fairness verification.

Each outcome is generated independently via ``secrets.randbelow`` with no
dependency on previous rounds.
"""

import secrets
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rng import RNGAuditLog

# ---------------------------------------------------------------------------
# Number-to-Color mapping constants
# ---------------------------------------------------------------------------

NUMBER_COLOR_MAP: dict[int, str] = {
    0: "violet",
    1: "green",
    2: "red",
    3: "green",
    4: "red",
    5: "violet",
    6: "red",
    7: "green",
    8: "red",
    9: "green",
}

GREEN_WINNING_NUMBERS: set[int] = {0, 1, 3, 5, 7, 9}
RED_WINNING_NUMBERS: set[int] = {2, 4, 6, 8}
VIOLET_WINNING_NUMBERS: set[int] = {0, 5}


@dataclass
class RNGResult:
    """Result of an RNG outcome generation."""

    raw_value: int
    num_options: int
    selected_color: str
    selected_number: int = 0
    algorithm: str = field(default="secrets.randbelow")


def generate_outcome(color_options: list[str] | None = None) -> RNGResult:
    """Generate a winning number 0–9 and derive the color from NUMBER_COLOR_MAP.

    The winning number is the primary source of truth. The color is derived
    from ``NUMBER_COLOR_MAP``. The ``color_options`` parameter is accepted
    for backward compatibility but is no longer used for outcome generation.

    Args:
        color_options: Kept for backward compatibility. Ignored when present.

    Returns:
        RNGResult with the selected number, derived color, and audit data.
    """
    winning_number = secrets.randbelow(10)
    selected_color = NUMBER_COLOR_MAP[winning_number]

    return RNGResult(
        raw_value=winning_number,
        num_options=10,
        selected_color=selected_color,
        selected_number=winning_number,
    )


async def create_audit_entry(
    session: AsyncSession,
    round_id: UUID,
    result: RNGResult,
) -> RNGAuditLog:
    """Record RNG result in the append-only audit log.

    Args:
        session: Async database session.
        round_id: The game round this outcome belongs to.
        result: The RNGResult to persist.

    Returns:
        The created RNGAuditLog row.
    """
    entry = RNGAuditLog(
        round_id=round_id,
        algorithm=result.algorithm,
        raw_value=result.raw_value,
        num_options=result.num_options,
        selected_color=result.selected_color,
    )
    session.add(entry)
    await session.flush()
    return entry
