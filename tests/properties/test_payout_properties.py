"""Property-based tests for payout calculator.

Uses Hypothesis to generate random test data for verifying payout invariants.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.services.payout_calculator import calculate_payout, calculate_round_payouts, check_reserve_threshold
from app.config import settings as app_settings


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

st_bet_amount = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("99999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

st_odds = st.decimals(
    min_value=Decimal("1.01"),
    max_value=Decimal("100.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

st_threshold = st.decimals(
    min_value=Decimal("1.00"),
    max_value=Decimal("999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

st_payout_amount = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("9999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


# ---------------------------------------------------------------------------
# Property 15: Payout calculation correctness
# For any bet amount A and odds O, payout = (A * O).quantize(Decimal("0.01"))
# using Decimal arithmetic.
# Validates: Requirements 6.1, 6.4
# ---------------------------------------------------------------------------


class TestProperty15PayoutCalculationCorrectness:
    """**Validates: Requirements 6.1, 6.4**"""

    @settings(max_examples=100)
    @given(bet_amount=st_bet_amount, odds=st_odds)
    def test_payout_equals_bet_times_odds_quantized(self, bet_amount, odds):
        """For any bet amount A and odds O, calculate_payout returns
        (A * 0.98 * O).quantize(Decimal("0.01")) using Decimal arithmetic,
        where 0.98 accounts for the 2% service fee."""
        result = calculate_payout(bet_amount, odds)
        effective = bet_amount * (Decimal("1") - Decimal("0.02"))
        expected = (effective * odds).quantize(Decimal("0.01"))
        assert result == expected

    @settings(max_examples=100)
    @given(bet_amount=st_bet_amount, odds=st_odds)
    def test_payout_has_two_decimal_places(self, bet_amount, odds):
        """Payout always has exactly two decimal places."""
        result = calculate_payout(bet_amount, odds)
        # Check that quantizing to 2 places is a no-op (already quantized)
        assert result == result.quantize(Decimal("0.01"))

    @settings(max_examples=100)
    @given(bet_amount=st_bet_amount, odds=st_odds)
    def test_payout_is_positive(self, bet_amount, odds):
        """Payout is always positive for positive bet and positive odds."""
        result = calculate_payout(bet_amount, odds)
        assert result > Decimal("0.00")


# ---------------------------------------------------------------------------
# Property 16: Reserve threshold flagging
# Round flagged when total payouts > threshold T; not flagged when <= T.
# Validates: Requirements 6.5
# ---------------------------------------------------------------------------


class TestProperty16ReserveThresholdFlagging:
    """**Validates: Requirements 6.5**"""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(data=st.data())
    def test_amount_above_threshold_is_flagged(self, monkeypatch, data):
        """When total payout exceeds the threshold, check_reserve_threshold
        returns True."""
        threshold = data.draw(st_threshold)
        monkeypatch.setattr(app_settings, "reserve_threshold", threshold)

        # Generate an amount strictly above the threshold
        above = data.draw(
            st.decimals(
                min_value=threshold + Decimal("0.01"),
                max_value=threshold + Decimal("100000.00"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )
        assert check_reserve_threshold(above) is True

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(data=st.data())
    def test_amount_at_or_below_threshold_not_flagged(self, monkeypatch, data):
        """When total payout is at or below the threshold, check_reserve_threshold
        returns False."""
        threshold = data.draw(st_threshold)
        monkeypatch.setattr(app_settings, "reserve_threshold", threshold)

        # Generate an amount at or below the threshold
        at_or_below = data.draw(
            st.decimals(
                min_value=Decimal("0.00"),
                max_value=threshold,
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )
        assert check_reserve_threshold(at_or_below) is False


# ---------------------------------------------------------------------------
# Feature: casino-ui-redesign, Property 3: Number bet payout correctness
# For any winning number w (0–9), any bet_number (0–9), and any bet_amount > 0:
# winner iff bet_number == w, payout = bet_amount * number_odds quantized to 2dp
# ---------------------------------------------------------------------------

# Strategies for Property 3
st_winning_number = st.integers(min_value=0, max_value=9)
st_bet_number = st.integers(min_value=0, max_value=9)
st_number_odds = st.decimals(
    min_value=Decimal("1.00"),
    max_value=Decimal("100.00"),
    places=1,
    allow_nan=False,
    allow_infinity=False,
)


def _make_number_bet(digit: int, amount: Decimal):
    """Create a mock Bet object for a number bet."""
    bet = MagicMock()
    bet.id = uuid4()
    bet.player_id = uuid4()
    bet.color = str(digit)
    bet.amount = amount
    bet.odds_at_placement = Decimal("9.6")
    bet.is_winner = None
    return bet


def _mock_session_with_bets(bets):
    """Create a mock AsyncSession that returns the given bets."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = bets
    session = AsyncMock()
    session.execute.return_value = mock_result
    return session


# ---------------------------------------------------------------------------
# Feature: casino-ui-redesign, Property 4: Color bet payout correctness with dual-color numbers
# For any winning number w (0–9) and any color bet (green/red/violet):
# verify correct winner determination per GREEN/RED/VIOLET_WINNING_NUMBERS sets,
# payout = bet_amount * color_odds quantized to 2dp
# ---------------------------------------------------------------------------

st_color_bet = st.sampled_from(["green", "red", "violet"])
st_color_odds = st.decimals(
    min_value=Decimal("1.00"),
    max_value=Decimal("100.00"),
    places=1,
    allow_nan=False,
    allow_infinity=False,
)

# Expected winning number sets (mirrors rng_engine constants)
_GREEN_WINS = {0, 1, 3, 5, 7, 9}
_RED_WINS = {2, 4, 6, 8}
_VIOLET_WINS = {0, 5}

_COLOR_WIN_MAP: dict[str, set[int]] = {
    "green": _GREEN_WINS,
    "red": _RED_WINS,
    "violet": _VIOLET_WINS,
}


def _make_color_bet(color: str, amount: Decimal):
    """Create a mock Bet object for a color bet."""
    bet = MagicMock()
    bet.id = uuid4()
    bet.player_id = uuid4()
    bet.color = color
    bet.amount = amount
    bet.odds_at_placement = Decimal("2.0")
    bet.is_winner = None
    return bet


class TestProperty4ColorBetPayoutCorrectnessWithDualColorNumbers:
    """**Validates: Requirements 8.3, 8.4**"""

    @settings(max_examples=100)
    @given(
        winning_number=st_winning_number,
        bet_color=st_color_bet,
        bet_amount=st_bet_amount,
        color_odds=st_color_odds,
    )
    @pytest.mark.asyncio
    async def test_color_bet_winner_determination_per_winning_number_sets(
        self, winning_number, bet_color, bet_amount, color_odds
    ):
        """A color bet wins iff the winning number is in the corresponding
        winning numbers set, and the payout equals bet_amount * color_odds
        quantized to 2dp."""
        bet = _make_color_bet(bet_color, bet_amount)
        session = _mock_session_with_bets([bet])

        odds = {
            "green": float(color_odds) if bet_color == "green" else 2.0,
            "red": float(color_odds) if bet_color == "red" else 2.0,
            "violet": float(color_odds) if bet_color == "violet" else 4.8,
            "number": 9.6,
        }
        # Override the specific color's odds to the generated value
        odds[bet_color] = float(color_odds)

        payouts = await calculate_round_payouts(
            session,
            uuid4(),
            "green",  # winning_color param (not used when winning_number provided)
            odds,
            winning_number=winning_number,
        )

        assert len(payouts) == 1
        payout = payouts[0]

        expected_winner = winning_number in _COLOR_WIN_MAP[bet_color]
        assert payout.is_winner is expected_winner

        if expected_winner:
            effective = bet_amount * (Decimal("1") - Decimal("0.02"))
            expected_amount = (effective * Decimal(str(color_odds))).quantize(
                Decimal("0.01")
            )
            assert payout.amount == expected_amount
        else:
            assert payout.amount == Decimal("0.00")

    @settings(max_examples=100)
    @given(
        winning_number=st_winning_number,
        bet_color=st_color_bet,
        bet_amount=st_bet_amount,
        color_odds=st_color_odds,
    )
    @pytest.mark.asyncio
    async def test_color_bet_payout_quantized_to_2dp(
        self, winning_number, bet_color, bet_amount, color_odds
    ):
        """Winning color bet payout always has exactly 2 decimal places."""
        # Only test winning cases to verify quantization
        if winning_number not in _COLOR_WIN_MAP[bet_color]:
            return  # skip non-winning combos for this sub-property

        bet = _make_color_bet(bet_color, bet_amount)
        session = _mock_session_with_bets([bet])

        odds = {"green": 2.0, "red": 2.0, "violet": 4.8, "number": 9.6}
        odds[bet_color] = float(color_odds)

        payouts = await calculate_round_payouts(
            session, uuid4(), "green", odds, winning_number=winning_number
        )

        payout = payouts[0]
        assert payout.is_winner is True
        assert payout.amount == payout.amount.quantize(Decimal("0.01"))

    @settings(max_examples=100)
    @given(
        winning_number=st_winning_number,
        bet_amount=st_bet_amount,
    )
    @pytest.mark.asyncio
    async def test_dual_color_numbers_pay_both_green_and_violet(
        self, winning_number, bet_amount
    ):
        """For dual-color numbers (0 and 5), both green and violet bets win."""
        if winning_number not in {0, 5}:
            return  # only test dual-color numbers

        green_bet = _make_color_bet("green", bet_amount)
        violet_bet = _make_color_bet("violet", bet_amount)
        red_bet = _make_color_bet("red", bet_amount)
        session = _mock_session_with_bets([green_bet, violet_bet, red_bet])

        odds = {"green": 2.0, "red": 2.0, "violet": 4.8, "number": 9.6}

        payouts = await calculate_round_payouts(
            session, uuid4(), "green", odds, winning_number=winning_number
        )

        assert len(payouts) == 3
        green_payout = payouts[0]
        violet_payout = payouts[1]
        red_payout = payouts[2]

        # Green and violet both win on 0 and 5
        assert green_payout.is_winner is True
        assert violet_payout.is_winner is True
        # Red never wins on 0 or 5
        assert red_payout.is_winner is False


class TestProperty3NumberBetPayoutCorrectness:
    """**Validates: Requirements 8.4**"""

    @settings(max_examples=100)
    @given(
        winning_number=st_winning_number,
        bet_number=st_bet_number,
        bet_amount=st_bet_amount,
        number_odds=st_number_odds,
    )
    @pytest.mark.asyncio
    async def test_number_bet_winner_iff_numbers_match(
        self, winning_number, bet_number, bet_amount, number_odds
    ):
        """A number bet wins if and only if bet_number == winning_number,
        and the payout equals bet_amount * number_odds quantized to 2dp."""
        bet = _make_number_bet(bet_number, bet_amount)
        session = _mock_session_with_bets([bet])

        odds = {
            "green": 2.0,
            "red": 2.0,
            "violet": 4.8,
            "number": float(number_odds),
        }

        payouts = await calculate_round_payouts(
            session,
            uuid4(),
            "green",  # winning_color irrelevant for number bets
            odds,
            winning_number=winning_number,
        )

        assert len(payouts) == 1
        payout = payouts[0]

        expected_winner = bet_number == winning_number
        assert payout.is_winner is expected_winner

        if expected_winner:
            effective = bet_amount * (Decimal("1") - Decimal("0.02"))
            expected_amount = (effective * Decimal(str(number_odds))).quantize(
                Decimal("0.01")
            )
            assert payout.amount == expected_amount
        else:
            assert payout.amount == Decimal("0.00")

    @settings(max_examples=100)
    @given(
        winning_number=st_winning_number,
        bet_amount=st_bet_amount,
        number_odds=st_number_odds,
    )
    @pytest.mark.asyncio
    async def test_number_bet_payout_quantized_to_2dp(
        self, winning_number, bet_amount, number_odds
    ):
        """Winning number bet payout always has exactly 2 decimal places."""
        bet = _make_number_bet(winning_number, bet_amount)
        session = _mock_session_with_bets([bet])

        odds = {"number": float(number_odds)}

        payouts = await calculate_round_payouts(
            session, uuid4(), "green", odds, winning_number=winning_number
        )

        payout = payouts[0]
        assert payout.is_winner is True
        assert payout.amount == payout.amount.quantize(Decimal("0.01"))
