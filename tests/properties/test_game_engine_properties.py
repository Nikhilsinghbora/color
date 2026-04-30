"""Property-based tests for the game engine service.

Uses Hypothesis to generate random test data for verifying game engine invariants.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import (
    BetLimitError,
    BettingClosedError,
    InsufficientBalanceError,
    InvalidTransitionError,
)
from app.models.game import GameMode, GameRound, RoundPhase
from app.models.player import Player, Wallet
from app.services import game_engine
from app.services.game_engine import VALID_TRANSITIONS, _validate_transition


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

st_round_phase = st.sampled_from(list(RoundPhase))


# ---------------------------------------------------------------------------
# Helpers — create fresh DB objects inside each Hypothesis iteration
# ---------------------------------------------------------------------------

async def _create_game_mode(
    session: AsyncSession,
    min_bet: Decimal = Decimal("1.00"),
    max_bet: Decimal = Decimal("1000.00"),
) -> GameMode:
    mode = GameMode(
        id=uuid4(),
        name=f"test-{uuid4().hex[:8]}",
        mode_type="classic",
        color_options=["red", "green", "blue"],
        odds={"red": 2.0, "green": 3.0, "blue": 5.0},
        min_bet=min_bet,
        max_bet=max_bet,
        round_duration_seconds=30,
    )
    session.add(mode)
    await session.flush()
    return mode


async def _create_player_with_wallet(
    session: AsyncSession,
    balance: Decimal = Decimal("500.00"),
) -> tuple[Player, Wallet]:
    player = Player(
        id=uuid4(),
        email=f"{uuid4().hex[:8]}@test.com",
        username=f"user-{uuid4().hex[:8]}",
        password_hash="hashed",
    )
    session.add(player)
    await session.flush()

    wallet = Wallet(
        id=uuid4(),
        player_id=player.id,
        balance=balance,
    )
    session.add(wallet)
    await session.flush()
    return player, wallet


# ---------------------------------------------------------------------------
# Property 8: Game round state machine validity
# Phase transitions only follow BETTING → RESOLUTION → RESULT;
# bets accepted only in BETTING phase.
# Validates: Requirements 3.1, 3.2, 3.3, 4.6
# ---------------------------------------------------------------------------


class TestProperty8StateMachineValidity:
    """**Validates: Requirements 3.1, 3.2, 3.3, 4.6**"""

    @settings(max_examples=100)
    @given(
        current=st_round_phase,
        target=st_round_phase,
    )
    async def test_only_valid_transitions_accepted(self, current, target):
        """For any pair of phases, only BETTING→RESOLUTION and RESOLUTION→RESULT
        are valid transitions; all others must raise InvalidTransitionError."""
        valid_pairs = {
            (RoundPhase.BETTING, RoundPhase.RESOLUTION),
            (RoundPhase.RESOLUTION, RoundPhase.RESULT),
        }

        if (current, target) in valid_pairs:
            # Should not raise
            _validate_transition(current, target)
        else:
            with pytest.raises(InvalidTransitionError):
                _validate_transition(current, target)

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(phase=st.sampled_from([RoundPhase.RESOLUTION, RoundPhase.RESULT]))
    async def test_bets_rejected_outside_betting_phase(self, session, phase):
        """Bets placed during RESOLUTION or RESULT phase must be rejected
        with BettingClosedError."""
        game_mode = await _create_game_mode(session)
        player, wallet = await _create_player_with_wallet(session)

        # Create a round and set its phase directly
        game_round = GameRound(
            id=uuid4(),
            game_mode_id=game_mode.id,
            phase=phase,
            betting_ends_at=datetime.now(timezone.utc) + timedelta(seconds=30),
        )
        session.add(game_round)
        await session.flush()

        with pytest.raises(BettingClosedError):
            await game_engine.place_bet(
                session, player.id, game_round.id, "red", Decimal("10.00")
            )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(data=st.data())
    async def test_bets_accepted_in_betting_phase(self, session, data):
        """Bets placed during BETTING phase with valid amount and balance
        must be accepted."""
        game_mode = await _create_game_mode(session)
        player, wallet = await _create_player_with_wallet(
            session, balance=Decimal("500.00")
        )

        amount = data.draw(
            st.decimals(
                min_value=Decimal("1.00"),
                max_value=Decimal("500.00"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )

        game_round = await game_engine.start_round(session, game_mode.id)
        assert game_round.phase == RoundPhase.BETTING

        bet = await game_engine.place_bet(
            session, player.id, game_round.id, "red", amount
        )
        assert bet is not None
        assert bet.amount == amount


# ---------------------------------------------------------------------------
# Property 9: Bet amount within configured limits
# Bet rejected if amount < min_bet or > max_bet; accepted if within range.
# Validates: Requirements 4.2
# ---------------------------------------------------------------------------


class TestProperty9BetLimits:
    """**Validates: Requirements 4.2**"""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(data=st.data())
    async def test_bet_below_min_rejected(self, session, data):
        """Any bet amount below min_bet must be rejected with BetLimitError."""
        min_bet = Decimal("1.00")
        game_mode = await _create_game_mode(session, min_bet=min_bet)
        player, wallet = await _create_player_with_wallet(
            session, balance=Decimal("10000.00")
        )

        amount = data.draw(
            st.decimals(
                min_value=Decimal("0.01"),
                max_value=Decimal("0.99"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )

        game_round = await game_engine.start_round(session, game_mode.id)

        with pytest.raises(BetLimitError) as exc_info:
            await game_engine.place_bet(
                session, player.id, game_round.id, "red", amount
            )
        assert exc_info.value.min_bet == min_bet

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(data=st.data())
    async def test_bet_above_max_rejected(self, session, data):
        """Any bet amount above max_bet must be rejected with BetLimitError."""
        max_bet = Decimal("1000.00")
        game_mode = await _create_game_mode(session, max_bet=max_bet)
        player, wallet = await _create_player_with_wallet(
            session, balance=Decimal("999999.00")
        )

        amount = data.draw(
            st.decimals(
                min_value=Decimal("1000.01"),
                max_value=Decimal("11000.00"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )

        game_round = await game_engine.start_round(session, game_mode.id)

        with pytest.raises(BetLimitError) as exc_info:
            await game_engine.place_bet(
                session, player.id, game_round.id, "red", amount
            )
        assert exc_info.value.max_bet == max_bet

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(data=st.data())
    async def test_bet_within_range_accepted(self, session, data):
        """Any bet amount within [min_bet, max_bet] and ≤ balance must pass
        limit validation."""
        min_bet = Decimal("1.00")
        max_bet = Decimal("1000.00")
        game_mode = await _create_game_mode(
            session, min_bet=min_bet, max_bet=max_bet
        )
        player, wallet = await _create_player_with_wallet(
            session, balance=Decimal("1000.00")
        )

        amount = data.draw(
            st.decimals(
                min_value=min_bet,
                max_value=max_bet,
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )

        game_round = await game_engine.start_round(session, game_mode.id)

        bet = await game_engine.place_bet(
            session, player.id, game_round.id, "red", amount
        )
        assert bet.amount == amount


# ---------------------------------------------------------------------------
# Property 10: Bet rejected when exceeding wallet balance
# Bet rejected with insufficient balance error when amount > wallet balance;
# balance unchanged.
# Validates: Requirements 4.3
# ---------------------------------------------------------------------------


class TestProperty10InsufficientBalance:
    """**Validates: Requirements 4.3**"""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    @given(data=st.data())
    async def test_bet_exceeding_balance_rejected(self, session, data):
        """Any bet where amount > wallet balance must be rejected with
        InsufficientBalanceError and the balance must remain unchanged."""
        balance = data.draw(
            st.decimals(
                min_value=Decimal("1.00"),
                max_value=Decimal("999.00"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )

        # Bet amount must exceed balance but stay within max_bet
        max_bet = Decimal("1000.00")
        lower = balance + Decimal("0.01")
        assume(lower <= max_bet)

        amount = data.draw(
            st.decimals(
                min_value=lower,
                max_value=max_bet,
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )

        game_mode = await _create_game_mode(
            session, min_bet=Decimal("0.01"), max_bet=max_bet
        )
        player, wallet = await _create_player_with_wallet(
            session, balance=balance
        )

        game_round = await game_engine.start_round(session, game_mode.id)

        with pytest.raises(InsufficientBalanceError) as exc_info:
            await game_engine.place_bet(
                session, player.id, game_round.id, "red", amount
            )

        assert exc_info.value.balance == balance
        assert exc_info.value.requested == amount

        # Verify balance is unchanged
        await session.refresh(wallet)
        assert wallet.balance == balance
