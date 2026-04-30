"""Game engine service — orchestrates round lifecycle, betting, and payouts.

State machine: BETTING → RESOLUTION → RESULT
Invalid transitions are rejected with InvalidTransitionError.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import (
    BetLimitError,
    BettingClosedError,
    InsufficientBalanceError,
    InvalidTransitionError,
)
from app.models.game import Bet, GameMode, GameRound, Payout, RoundPhase
from app.services import payout_calculator, rng_engine, wallet_service


# Valid state transitions
VALID_TRANSITIONS: dict[RoundPhase, RoundPhase] = {
    RoundPhase.BETTING: RoundPhase.RESOLUTION,
    RoundPhase.RESOLUTION: RoundPhase.RESULT,
}


@dataclass
class RoundState:
    """Snapshot of a round's current state for WebSocket broadcast."""
    round_id: UUID
    game_mode_id: UUID
    phase: RoundPhase
    winning_color: Optional[str]
    total_bets: Decimal
    total_payouts: Decimal
    betting_ends_at: datetime
    resolved_at: Optional[datetime]
    completed_at: Optional[datetime]


def _validate_transition(current: RoundPhase, target: RoundPhase) -> None:
    """Raise InvalidTransitionError if the transition is not allowed."""
    expected = VALID_TRANSITIONS.get(current)
    if expected != target:
        raise InvalidTransitionError(current.value, target.value)


async def start_round(session: AsyncSession, game_mode_id: UUID) -> GameRound:
    """Create a new round in BETTING phase.

    Args:
        session: Async database session.
        game_mode_id: The game mode to use for this round.

    Returns:
        The newly created GameRound in BETTING phase.
    """
    result = await session.execute(
        select(GameMode).where(GameMode.id == game_mode_id)
    )
    game_mode = result.scalar_one()

    now = datetime.now(timezone.utc)
    betting_ends_at = now + timedelta(seconds=game_mode.round_duration_seconds)

    game_round = GameRound(
        game_mode_id=game_mode_id,
        phase=RoundPhase.BETTING,
        betting_ends_at=betting_ends_at,
    )
    session.add(game_round)
    await session.flush()
    return game_round


async def place_bet(
    session: AsyncSession,
    player_id: UUID,
    round_id: UUID,
    color: str,
    amount: Decimal,
) -> Bet:
    """Place a bet on a color for a given round.

    Validates:
    - Round is in BETTING phase
    - Bet amount is within game mode min_bet/max_bet limits
    - Player has sufficient wallet balance
    - Deducts bet from wallet

    Args:
        session: Async database session.
        player_id: The player placing the bet.
        round_id: The round to bet on.
        color: The color being bet on.
        amount: The bet amount.

    Returns:
        The created Bet record.

    Raises:
        BettingClosedError: If round is not in BETTING phase.
        BetLimitError: If amount is outside min_bet/max_bet.
        InsufficientBalanceError: If wallet balance is insufficient.
    """
    # Fetch round and validate phase
    round_result = await session.execute(
        select(GameRound).where(GameRound.id == round_id)
    )
    game_round = round_result.scalar_one()

    if game_round.phase != RoundPhase.BETTING:
        raise BettingClosedError(game_round.phase.value)

    # Fetch game mode for bet limits and odds
    mode_result = await session.execute(
        select(GameMode).where(GameMode.id == game_round.game_mode_id)
    )
    game_mode = mode_result.scalar_one()

    # Validate bet amount against min/max limits
    min_bet = Decimal(str(game_mode.min_bet))
    max_bet = Decimal(str(game_mode.max_bet))
    if amount < min_bet or amount > max_bet:
        raise BetLimitError(amount, min_bet, max_bet)

    # Validate color: must be a known color name or a single digit "0"–"9"
    valid_colors = set(game_mode.color_options)
    valid_digits = {str(d) for d in range(10)}
    if color not in valid_colors and color not in valid_digits:
        raise ValueError(
            f"Invalid bet choice '{color}'. Must be a valid color or digit 0-9."
        )

    # Validate wallet balance
    balance = await wallet_service.get_balance(session, player_id)
    if balance < amount:
        raise InsufficientBalanceError(balance=balance, requested=amount)

    # Deduct from wallet
    await wallet_service.debit(session, player_id, amount, round_id)

    # Get odds for the chosen color/number
    if color in valid_digits:
        odds_value = Decimal(str(game_mode.odds.get("number", 0)))
    else:
        odds_value = Decimal(str(game_mode.odds.get(color, 0)))

    # Create bet record
    bet = Bet(
        player_id=player_id,
        round_id=round_id,
        color=color,
        amount=amount,
        odds_at_placement=odds_value,
    )
    session.add(bet)

    # Update round total bets
    game_round.total_bets = (game_round.total_bets or Decimal("0.00")) + amount

    await session.flush()
    return bet


async def resolve_round(session: AsyncSession, round_id: UUID) -> GameRound:
    """Invoke RNG and transition round to RESOLUTION phase.

    Args:
        session: Async database session.
        round_id: The round to resolve.

    Returns:
        The updated GameRound in RESOLUTION phase.

    Raises:
        InvalidTransitionError: If round is not in BETTING phase.
    """
    result = await session.execute(
        select(GameRound).where(GameRound.id == round_id)
    )
    game_round = result.scalar_one()

    _validate_transition(game_round.phase, RoundPhase.RESOLUTION)

    # Fetch game mode for color options
    mode_result = await session.execute(
        select(GameMode).where(GameMode.id == game_round.game_mode_id)
    )
    game_mode = mode_result.scalar_one()

    # Generate RNG outcome
    rng_result = rng_engine.generate_outcome(game_mode.color_options)

    # Record audit entry
    await rng_engine.create_audit_entry(session, round_id, rng_result)

    # Update round
    game_round.phase = RoundPhase.RESOLUTION
    game_round.winning_color = rng_result.selected_color
    game_round.winning_number = rng_result.selected_number
    game_round.resolved_at = datetime.now(timezone.utc)

    await session.flush()
    return game_round


async def finalize_round(session: AsyncSession, round_id: UUID) -> GameRound:
    """Calculate payouts, credit winners, transition to RESULT phase.

    Args:
        session: Async database session.
        round_id: The round to finalize.

    Returns:
        The updated GameRound in RESULT phase.

    Raises:
        InvalidTransitionError: If round is not in RESOLUTION phase.
    """
    result = await session.execute(
        select(GameRound).where(GameRound.id == round_id)
    )
    game_round = result.scalar_one()

    _validate_transition(game_round.phase, RoundPhase.RESULT)

    # Fetch game mode for odds
    mode_result = await session.execute(
        select(GameMode).where(GameMode.id == game_round.game_mode_id)
    )
    game_mode = mode_result.scalar_one()

    # Calculate payouts for all bets
    payout_results = await payout_calculator.calculate_round_payouts(
        session, round_id, game_round.winning_color, game_mode.odds,
        winning_number=game_round.winning_number,
    )

    total_payout = Decimal("0.00")
    for pr in payout_results:
        if pr.is_winner and pr.amount > 0:
            # Credit winner wallet
            await wallet_service.credit(session, pr.player_id, pr.amount, round_id)

            # Create payout record
            payout = Payout(
                bet_id=pr.bet_id,
                player_id=pr.player_id,
                round_id=round_id,
                amount=pr.amount,
                credited=True,
            )
            session.add(payout)
            total_payout += pr.amount

    # Update round totals
    game_round.total_payouts = total_payout
    game_round.phase = RoundPhase.RESULT
    game_round.completed_at = datetime.now(timezone.utc)

    # Check reserve threshold
    if payout_calculator.check_reserve_threshold(total_payout):
        game_round.flagged_for_review = True

    await session.flush()
    return game_round


async def get_round_state(session: AsyncSession, round_id: UUID) -> RoundState:
    """Return the current round state for WebSocket broadcast.

    Args:
        session: Async database session.
        round_id: The round to query.

    Returns:
        RoundState snapshot of the current round.
    """
    result = await session.execute(
        select(GameRound).where(GameRound.id == round_id)
    )
    game_round = result.scalar_one()

    return RoundState(
        round_id=game_round.id,
        game_mode_id=game_round.game_mode_id,
        phase=game_round.phase,
        winning_color=game_round.winning_color,
        total_bets=game_round.total_bets,
        total_payouts=game_round.total_payouts,
        betting_ends_at=game_round.betting_ends_at,
        resolved_at=game_round.resolved_at,
        completed_at=game_round.completed_at,
    )
