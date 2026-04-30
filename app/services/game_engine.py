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
from app.services import payout_calculator, profit_service, rng_engine, wallet_service
from app.services.period_number import generate_period_number


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
    period_number: Optional[str] = None


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

    # Generate and assign period number
    period_number = await generate_period_number(
        session, game_mode.id, game_mode.mode_prefix
    )
    game_round.period_number = period_number

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

    # Validate color: must be a known color name, a single digit "0"–"9",
    # or a big/small bet type
    valid_colors = set(game_mode.color_options)
    valid_digits = {str(d) for d in range(10)}
    valid_big_small = {"big", "small"}
    if color not in valid_colors and color not in valid_digits and color not in valid_big_small:
        raise ValueError(
            f"Invalid bet choice '{color}'. Must be a valid color, digit 0-9, or 'big'/'small'."
        )

    # Validate wallet balance
    balance = await wallet_service.get_balance(session, player_id)
    if balance < amount:
        raise InsufficientBalanceError(balance=balance, requested=amount)

    # Deduct from wallet
    await wallet_service.debit(session, player_id, amount, round_id)

    # Get odds for the chosen color/number/big/small
    if color in valid_big_small:
        odds_value = Decimal(str(game_mode.odds.get(color, 0)))
    elif color in valid_digits:
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

    Uses profit management system to:
    1. Calculate house profit and winner pool from total bets
    2. Calculate all winner payouts based on odds
    3. If payouts exceed winner pool, reduce proportionally
    4. Credit winners with adjusted amounts

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

    # Step 1: Calculate profit allocation (house profit vs winner pool)
    profit_allocation = await profit_service.calculate_profit_allocation(
        session, game_round.total_bets
    )

    # Step 2: Calculate all winner payouts based on odds
    payout_results = await payout_calculator.calculate_round_payouts(
        session, round_id, game_round.winning_color, game_mode.odds,
        winning_number=game_round.winning_number,
    )

    # Step 3: Sum up total calculated payouts
    total_calculated_payouts = sum(
        pr.amount for pr in payout_results if pr.is_winner
    )

    # Step 4: Adjust payouts to fit within winner pool if necessary
    adjustment = profit_service.adjust_payouts_to_pool(
        total_calculated_payouts,
        profit_allocation.winners_pool_amount,
    )

    # Step 5: Credit winners with adjusted amounts
    total_actual_payout = Decimal("0.00")
    for pr in payout_results:
        if pr.is_winner and pr.amount > 0:
            # Apply reduction ratio if payouts were reduced
            adjusted_amount = (pr.amount * adjustment.reduction_ratio).quantize(Decimal("0.01"))

            # Credit winner wallet with adjusted amount
            await wallet_service.credit(session, pr.player_id, adjusted_amount, round_id)

            # Create payout record
            payout = Payout(
                bet_id=pr.bet_id,
                player_id=pr.player_id,
                round_id=round_id,
                amount=adjusted_amount,
                credited=True,
            )
            session.add(payout)
            total_actual_payout += adjusted_amount

    # Step 6: Update round with profit management details
    game_round.total_payouts = total_actual_payout
    game_round.phase = RoundPhase.RESULT
    game_round.completed_at = datetime.now(timezone.utc)

    # Profit management fields
    game_round.total_payout_pool = profit_allocation.winners_pool_amount
    game_round.house_profit = profit_allocation.house_profit_amount
    game_round.total_calculated_payouts = total_calculated_payouts
    game_round.payout_reduced = adjustment.payout_reduced
    game_round.applied_house_percentage = profit_allocation.house_profit_percentage
    game_round.applied_winners_percentage = profit_allocation.winners_pool_percentage

    # Flag for review if payouts were reduced
    if adjustment.payout_reduced:
        game_round.flagged_for_review = True

    # Also check old reserve threshold for backwards compatibility
    if payout_calculator.check_reserve_threshold(total_actual_payout):
        game_round.flagged_for_review = True

    await session.flush()
    return game_round


async def get_active_round_for_mode(
    session: AsyncSession, game_mode_id: UUID
) -> Optional[GameRound]:
    """Return the most recent BETTING or RESOLUTION round for a game mode.

    Args:
        session: Async database session.
        game_mode_id: The game mode to look up.

    Returns:
        The most recent active GameRound, or None if no active round exists.
    """
    result = await session.execute(
        select(GameRound)
        .where(
            GameRound.game_mode_id == game_mode_id,
            GameRound.phase.in_([RoundPhase.BETTING, RoundPhase.RESOLUTION]),
        )
        .order_by(GameRound.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


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
        period_number=game_round.period_number,
    )


async def broadcast_bet_update(session: AsyncSession, round_id: UUID) -> None:
    """Broadcast bet update message to all clients after a bet is placed.

    This notifies clients that the total players count and total pool have changed.

    Args:
        session: Async database session.
        round_id: The round that received a new bet.
    """
    import json
    from datetime import datetime, timezone

    import redis.asyncio as aioredis

    from app.config import settings
    from app.services.bot_service import bot_service

    # Get current round state
    result = await session.execute(
        select(GameRound).where(GameRound.id == round_id)
    )
    game_round = result.scalar_one()

    # Count real players who have bet on this round
    from sqlalchemy import func

    real_player_count_result = await session.execute(
        select(func.count(func.distinct(Bet.player_id))).where(Bet.round_id == round_id)
    )
    real_player_count = real_player_count_result.scalar_one()

    # Get bot stats for this round
    bot_stats = bot_service.get_bot_stats_for_round(round_id)

    # Prepare the bet_update message
    payload = {
        "type": "bet_update",
        "round_id": str(round_id),
        "total_players": real_player_count + bot_stats["total_bots"],
        "total_pool": str(game_round.total_bets + bot_stats["total_bet_amount"]),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Publish to Redis pub/sub
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        channel = f"channel:round:{round_id}"
        await client.publish(channel, json.dumps(payload))
    finally:
        await client.aclose()
