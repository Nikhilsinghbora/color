"""Payout calculator service using Decimal fixed-point arithmetic.

All payout calculations use Python's Decimal type with quantize("0.01")
to guarantee two-decimal-place precision.  Float arithmetic is never used.

Functions:
    calculate_payout      – single bet payout (bet_amount × odds)
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


@dataclass
class PayoutResult:
    """Result of a payout calculation for a single bet."""
    bet_id: UUID
    player_id: UUID
    amount: Decimal
    is_winner: bool


def calculate_payout(bet_amount: Decimal, odds: Decimal) -> Decimal:
    """Calculate payout as bet_amount * odds, quantized to 2 decimal places.

    Uses Decimal arithmetic exclusively — never float.
    """
    return (bet_amount * odds).quantize(Decimal("0.01"))


def _is_number_bet(color: str) -> bool:
    """Return True if the bet color field is a digit string ("0"–"9")."""
    return len(color) == 1 and color.isdigit()


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
        if _is_number_bet(bet.color):
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
