"""Property-based tests for number bet acceptance and validation.

# Feature: casino-ui-redesign, Property 5: Number bet acceptance and validation
# For any digit string "0"–"9" and any amount: accepted iff min_bet <= amount <= max_bet
# and sufficient balance.

Uses Hypothesis with real async DB sessions to verify the game engine's
place_bet() correctly accepts or rejects number bets.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import BetLimitError, InsufficientBalanceError
from app.models.game import GameMode, GameRound, RoundPhase
from app.models.player import Player, Wallet
from app.services import game_engine


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
        color_options=["red", "green", "violet"],
        odds={"red": 2.0, "green": 2.0, "violet": 4.8, "number": 9.6},
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
# Strategies
# ---------------------------------------------------------------------------

st_digit = st.sampled_from([str(d) for d in range(10)])


# ---------------------------------------------------------------------------
# Feature: casino-ui-redesign, Property 5: Number bet acceptance and validation
# For any digit string "0"–"9" and any amount: accepted iff
# min_bet <= amount <= max_bet and sufficient balance.
# ---------------------------------------------------------------------------


class TestProperty5NumberBetAcceptanceAndValidation:
    """**Validates: Requirements 8.2**"""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        digit=st_digit,
        data=st.data(),
    )
    async def test_number_bet_accepted_when_within_limits_and_sufficient_balance(
        self, session, digit, data
    ):
        """For any digit "0"–"9", a bet with min_bet <= amount <= max_bet
        and amount <= balance is accepted."""
        min_bet = Decimal("1.00")
        max_bet = Decimal("1000.00")
        game_mode = await _create_game_mode(session, min_bet=min_bet, max_bet=max_bet)

        amount = data.draw(
            st.decimals(
                min_value=min_bet,
                max_value=max_bet,
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )

        player, wallet = await _create_player_with_wallet(
            session, balance=max_bet,
        )

        game_round = await game_engine.start_round(session, game_mode.id)

        bet = await game_engine.place_bet(
            session, player.id, game_round.id, digit, amount
        )
        assert bet is not None
        assert bet.color == digit
        assert bet.amount == amount
        assert bet.odds_at_placement == Decimal("9.6")

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        digit=st_digit,
        data=st.data(),
    )
    async def test_number_bet_rejected_when_below_min_bet(
        self, session, digit, data
    ):
        """For any digit "0"–"9", a bet with amount < min_bet is rejected
        with BetLimitError."""
        min_bet = Decimal("1.00")
        max_bet = Decimal("1000.00")
        game_mode = await _create_game_mode(session, min_bet=min_bet, max_bet=max_bet)

        amount = data.draw(
            st.decimals(
                min_value=Decimal("0.01"),
                max_value=Decimal("0.99"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )

        player, wallet = await _create_player_with_wallet(
            session, balance=Decimal("10000.00"),
        )

        game_round = await game_engine.start_round(session, game_mode.id)

        with pytest.raises(BetLimitError) as exc_info:
            await game_engine.place_bet(
                session, player.id, game_round.id, digit, amount
            )
        assert exc_info.value.min_bet == min_bet

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        digit=st_digit,
        data=st.data(),
    )
    async def test_number_bet_rejected_when_above_max_bet(
        self, session, digit, data
    ):
        """For any digit "0"–"9", a bet with amount > max_bet is rejected
        with BetLimitError."""
        min_bet = Decimal("1.00")
        max_bet = Decimal("1000.00")
        game_mode = await _create_game_mode(session, min_bet=min_bet, max_bet=max_bet)

        amount = data.draw(
            st.decimals(
                min_value=Decimal("1000.01"),
                max_value=Decimal("11000.00"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )

        player, wallet = await _create_player_with_wallet(
            session, balance=Decimal("999999.00"),
        )

        game_round = await game_engine.start_round(session, game_mode.id)

        with pytest.raises(BetLimitError) as exc_info:
            await game_engine.place_bet(
                session, player.id, game_round.id, digit, amount
            )
        assert exc_info.value.max_bet == max_bet

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    @given(
        digit=st_digit,
        data=st.data(),
    )
    async def test_number_bet_rejected_when_insufficient_balance(
        self, session, digit, data
    ):
        """For any digit "0"–"9", a bet with amount > balance (but within
        bet limits) is rejected with InsufficientBalanceError."""
        min_bet = Decimal("1.00")
        max_bet = Decimal("1000.00")

        balance = data.draw(
            st.decimals(
                min_value=min_bet,
                max_value=Decimal("999.00"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )

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
            session, min_bet=min_bet, max_bet=max_bet
        )
        player, wallet = await _create_player_with_wallet(
            session, balance=balance,
        )

        game_round = await game_engine.start_round(session, game_mode.id)

        with pytest.raises(InsufficientBalanceError) as exc_info:
            await game_engine.place_bet(
                session, player.id, game_round.id, digit, amount
            )
        assert exc_info.value.balance == balance
        assert exc_info.value.requested == amount

        # Verify balance unchanged
        await session.refresh(wallet)
        assert wallet.balance == balance
