"""Profit-margin-aware outcome selection engine.

Instead of picking a purely random number and hoping the house margin holds,
this engine:

1. Examines every bet placed in the round.
2. For each candidate winning number (0–9), simulates the total payout.
3. Picks the number that keeps the house profit closest to (or above) the
   admin-configured margin.
4. Falls back to pure CSPRNG only when no bets exist (nothing to optimise).

The admin sets a profit/distribution split (e.g. 20/80).  The engine
guarantees the house keeps *at least* that percentage of the pot whenever
mathematically possible.  When every candidate number would bust the margin
(rare, small-pool edge case), the engine picks the number with the lowest
payout — minimising loss.

An RNG audit log entry is still created for every round so the audit trail
remains intact.

All arithmetic uses ``Decimal`` — no floats.
"""

import secrets
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Bet, GameMode
from app.services.payout_calculator import (
    BIG_NUMBERS,
    SMALL_NUMBERS,
    SERVICE_FEE_RATE,
    calculate_payout,
)
from app.services.rng_engine import (
    GREEN_WINNING_NUMBERS,
    NUMBER_COLOR_MAP,
    RED_WINNING_NUMBERS,
    RNGResult,
    VIOLET_WINNING_NUMBERS,
    create_audit_entry,
)


@dataclass
class CandidateOutcome:
    """Simulated outcome for a single candidate number."""

    number: int
    color: str
    total_payout: Decimal
    house_profit: Decimal          # total_bets - total_payout
    house_profit_pct: Decimal      # (house_profit / total_bets) * 100
    meets_margin: bool             # house_profit_pct >= target margin


def _bet_wins(bet_color: str, winning_number: int) -> bool:
    """Return True if *bet_color* wins when *winning_number* is drawn."""
    # Number bet ("0"–"9")
    if len(bet_color) == 1 and bet_color.isdigit():
        return int(bet_color) == winning_number
    # Big / small
    if bet_color == "big":
        return winning_number in BIG_NUMBERS
    if bet_color == "small":
        return winning_number in SMALL_NUMBERS
    # Color bet
    if bet_color == "green":
        return winning_number in GREEN_WINNING_NUMBERS
    if bet_color == "red":
        return winning_number in RED_WINNING_NUMBERS
    if bet_color == "violet":
        return winning_number in VIOLET_WINNING_NUMBERS
    return False


def _simulate_payouts(
    bets: list[Bet],
    winning_number: int,
    odds: dict[str, float],
) -> Decimal:
    """Return the total payout if *winning_number* is drawn."""
    total = Decimal("0.00")
    for bet in bets:
        if not _bet_wins(bet.color, winning_number):
            continue
        # Determine the odds key for this bet type
        if len(bet.color) == 1 and bet.color.isdigit():
            bet_odds = Decimal(str(odds.get("number", 0)))
        elif bet.color in ("big", "small"):
            bet_odds = Decimal(str(odds.get(bet.color, 0)))
        else:
            bet_odds = Decimal(str(odds.get(bet.color, 0)))
        total += calculate_payout(bet.amount, bet_odds)
    return total


def evaluate_candidates(
    bets: list[Bet],
    total_bets: Decimal,
    odds: dict[str, float],
    target_house_pct: Decimal,
) -> list[CandidateOutcome]:
    """Score every candidate number 0–9 against the target house margin."""
    candidates: list[CandidateOutcome] = []
    for num in range(10):
        payout = _simulate_payouts(bets, num, odds)
        profit = total_bets - payout
        if total_bets > 0:
            profit_pct = (profit / total_bets * Decimal("100")).quantize(Decimal("0.01"))
        else:
            profit_pct = Decimal("100.00")
        candidates.append(CandidateOutcome(
            number=num,
            color=NUMBER_COLOR_MAP[num],
            total_payout=payout,
            house_profit=profit,
            house_profit_pct=profit_pct,
            meets_margin=profit_pct >= target_house_pct,
        ))
    return candidates


async def select_outcome(
    session: AsyncSession,
    round_id: UUID,
    game_mode: GameMode,
    total_bets: Decimal,
    target_house_pct: Decimal,
) -> RNGResult:
    """Pick the winning number that satisfies the house profit margin.

    Algorithm:
    1. If no bets exist → pure random (nothing to optimise).
    2. Evaluate all 10 candidates.
    3. Collect candidates that meet the target margin.
       a. If multiple meet it → pick one at random (keeps outcomes
          unpredictable to players while guaranteeing margin).
       b. If none meet it → pick the candidate with the *highest*
          house profit (minimise loss).
    4. Record an RNG audit entry and return the result.
    """
    # Fetch all bets for this round
    result = await session.execute(
        select(Bet).where(Bet.round_id == round_id)
    )
    bets = list(result.scalars().all())

    if not bets:
        # No bets — pure random, nothing to optimise
        winning_number = secrets.randbelow(10)
    else:
        candidates = evaluate_candidates(
            bets, total_bets, game_mode.odds, target_house_pct,
        )

        # Candidates that meet the margin
        good = [c for c in candidates if c.meets_margin]

        if good:
            # Randomly pick among the profitable candidates
            chosen = good[secrets.randbelow(len(good))]
        else:
            # None meet the margin — pick the least-loss candidate
            candidates.sort(key=lambda c: c.house_profit, reverse=True)
            chosen = candidates[0]

        winning_number = chosen.number

    selected_color = NUMBER_COLOR_MAP[winning_number]

    rng_result = RNGResult(
        raw_value=winning_number,
        num_options=10,
        selected_color=selected_color,
        selected_number=winning_number,
        algorithm="profit_margin_selection",
    )

    # Audit trail
    await create_audit_entry(session, round_id, rng_result)

    return rng_result
