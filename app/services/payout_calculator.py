"""Payout calculator service using Decimal fixed-point arithmetic.

All payout calculations use Python's Decimal type with quantize("0.01")
to guarantee two-decimal-place precision.  Float arithmetic is never used.

Functions:
    calculate_payout      – single bet payout with service fee
    calculate_round_payouts – all payouts for a completed round
    check_reserve_threshold – flag rounds exceeding the reserve limit
"""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.game import Bet, Payout
from app.services.rng_engine import GREEN_WINNING_NUMBERS, RED_WINNING_NUMBERS, VIOLET_WINNING_NUMBERS

# ---------------------------------------------------------------------------
# Configurable constants
# ---------------------------------------------------------------------------

SERVICE_FEE_RATE: Decimal = Decimal("0.02")
"""2% service fee deducted from bet amount before payout calculation."""

BIG_NUMBERS: set[int] = {5, 6, 7, 8, 9}
"""Numbers that qualify as "big" for big/small bets."""

SMALL_NUMBERS: set[int] = {0, 1, 2, 3, 4}
"""Numbers that qualify as "small" for big/small bets."""


@dataclass
class PayoutResult:
    """Result of a payout calculation for a single bet."""
    bet_id: UUID
    player_id: UUID
    amount: Decimal
    is_winner: bool


def calculate_payout(bet_amount: Decimal, odds: Decimal) -> Decimal:
    """Calculate payout with service fee: (bet_amount × (1 - SERVICE_FEE_RATE)) × odds.

    The service fee is deducted from the bet amount before multiplying by odds.
    Uses Decimal arithmetic exclusively — never float.
    """
    effective_amount = bet_amount * (Decimal("1") - SERVICE_FEE_RATE)
    return (effective_amount * odds).quantize(Decimal("0.01"))


def _is_number_bet(color: str) -> bool:
    """Return True if the bet color field is a digit string ("0"–"9")."""
    return len(color) == 1 and color.isdigit()


def _is_big_small_bet(color: str) -> bool:
    """Return True if the bet color field is "big" or "small"."""
    return color in ("big", "small")


def _is_big_small_winner(bet_type: str, winning_number: int) -> bool:
    """Determine if a big/small bet wins given the winning number.

    "big" wins when winning_number is in {5, 6, 7, 8, 9}.
    "small" wins when winning_number is in {0, 1, 2, 3, 4}.
    """
    if bet_type == "big":
        return winning_number in BIG_NUMBERS
    if bet_type == "small":
        return winning_number in SMALL_NUMBERS
    return False


def _is_color_winner(bet_color: str, winning_number: int) -> bool:
    """Determine if a color bet wins given the winning number.

    Green wins when winning_number is in {0,1,3,5,7,9}.
    Red wins when winning_number is in {2,4,6,8}.
    Violet wins when winning_number is in {0,5}.
    """
    if bet_color == "green":
        return winning_number in GREEN_WINNING_NUMBERS
    if bet_color == "red":
        return winning_number in RED_WINNING_NUMBERS
    if bet_color == "violet":
        return winning_number in VIOLET_WINNING_NUMBERS
    return False


async def calculate_round_payouts(
    session: AsyncSession,
    round_id: UUID,
    winning_color: str,
    odds: dict[str, float],
    winning_number: int | None = None,
) -> list[PayoutResult]:
    """Compute all payouts for a round based on the winning number and color.

    Supports both number bets (digit strings "0"–"9") and color bets.
    When ``winning_number`` is provided, color-bet winners are determined
    by the number-to-color mapping sets (GREEN/RED/VIOLET_WINNING_NUMBERS)
    rather than simple string equality, enabling dual-color payouts for
    numbers 0 and 5.
    """
    result = await session.execute(
        select(Bet).where(Bet.round_id == round_id)
    )
    bets = result.scalars().all()

    payouts: list[PayoutResult] = []
    for bet in bets:
        if _is_big_small_bet(bet.color):
            # Big/Small bet: winner determined by number range
            is_winner = (
                winning_number is not None
                and _is_big_small_winner(bet.color, winning_number)
            )
            if is_winner:
                bs_odds = Decimal(str(odds.get(bet.color, 0)))
                payout_amount = calculate_payout(bet.amount, bs_odds)
            else:
                payout_amount = Decimal("0.00")
        elif _is_number_bet(bet.color):
            # Number bet: winner iff the digit matches the winning number
            is_winner = (
                winning_number is not None
                and int(bet.color) == winning_number
            )
            if is_winner:
                number_odds = Decimal(str(odds.get("number", 0)))
                payout_amount = calculate_payout(bet.amount, number_odds)
            else:
                payout_amount = Decimal("0.00")
        else:
            # Color bet
            if winning_number is not None:
                is_winner = _is_color_winner(bet.color, winning_number)
            else:
                # Fallback for legacy rounds without winning_number
                is_winner = bet.color == winning_color
            if is_winner:
                color_odds = Decimal(str(odds.get(bet.color, 0)))
                payout_amount = calculate_payout(bet.amount, color_odds)
            else:
                payout_amount = Decimal("0.00")

        bet.is_winner = is_winner

        payouts.append(PayoutResult(
            bet_id=bet.id,
            player_id=bet.player_id,
            amount=payout_amount,
            is_winner=is_winner,
        ))

    return payouts


def check_reserve_threshold(total_payout: Decimal) -> bool:
    """Return True if total payout exceeds the configured reserve limit."""
    return total_payout > settings.reserve_threshold
