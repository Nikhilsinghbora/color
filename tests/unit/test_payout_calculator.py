"""Unit tests for payout calculator service.

Tests cover:
- calculate_payout: Decimal arithmetic, quantization, edge cases
- calculate_round_payouts: winner/loser classification, payout amounts,
  number bets, dual-color numbers (0 and 5)
- check_reserve_threshold: threshold comparison logic
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.payout_calculator import (
    BIG_NUMBERS,
    SMALL_NUMBERS,
    SERVICE_FEE_RATE,
    PayoutResult,
    _is_big_small_bet,
    _is_big_small_winner,
    _is_color_winner,
    _is_number_bet,
    calculate_payout,
    calculate_round_payouts,
    check_reserve_threshold,
)


# ---------------------------------------------------------------------------
# calculate_payout
# ---------------------------------------------------------------------------

class TestCalculatePayout:
    """Tests for the single-bet payout calculation."""

    def test_basic_multiplication(self):
        # 100 × 0.98 × 2.00 = 196.00
        result = calculate_payout(Decimal("100.00"), Decimal("2.00"))
        assert result == Decimal("196.00")

    def test_quantizes_to_two_decimal_places(self):
        # 33.33 × 0.98 × 3.33 = 108.7693..., quantized to 108.77
        result = calculate_payout(Decimal("33.33"), Decimal("3.33"))
        expected = (Decimal("33.33") * Decimal("0.98") * Decimal("3.33")).quantize(Decimal("0.01"))
        assert result == expected
        assert result.as_tuple().exponent == -2

    def test_zero_bet_returns_zero(self):
        result = calculate_payout(Decimal("0.00"), Decimal("5.00"))
        assert result == Decimal("0.00")

    def test_zero_odds_returns_zero(self):
        result = calculate_payout(Decimal("50.00"), Decimal("0.00"))
        assert result == Decimal("0.00")

    def test_returns_decimal_type(self):
        result = calculate_payout(Decimal("10.00"), Decimal("1.50"))
        assert isinstance(result, Decimal)

    def test_large_bet_large_odds(self):
        result = calculate_payout(Decimal("99999.99"), Decimal("99.99"))
        expected = (Decimal("99999.99") * Decimal("0.98") * Decimal("99.99")).quantize(Decimal("0.01"))
        assert result == expected

    def test_fractional_odds(self):
        # 10.00 × 0.98 × 1.50 = 14.70
        result = calculate_payout(Decimal("10.00"), Decimal("1.50"))
        assert result == Decimal("14.70")

    def test_small_amounts(self):
        result = calculate_payout(Decimal("0.01"), Decimal("2.00"))
        assert result == Decimal("0.02")


# ---------------------------------------------------------------------------
# check_reserve_threshold
# ---------------------------------------------------------------------------

class TestCheckReserveThreshold:
    """Tests for reserve threshold flagging."""

    @patch("app.services.payout_calculator.settings")
    def test_exceeds_threshold_returns_true(self, mock_settings):
        mock_settings.reserve_threshold = Decimal("100000.00")
        assert check_reserve_threshold(Decimal("100000.01")) is True

    @patch("app.services.payout_calculator.settings")
    def test_equals_threshold_returns_false(self, mock_settings):
        mock_settings.reserve_threshold = Decimal("100000.00")
        assert check_reserve_threshold(Decimal("100000.00")) is False

    @patch("app.services.payout_calculator.settings")
    def test_below_threshold_returns_false(self, mock_settings):
        mock_settings.reserve_threshold = Decimal("100000.00")
        assert check_reserve_threshold(Decimal("50000.00")) is False

    @patch("app.services.payout_calculator.settings")
    def test_zero_payout_returns_false(self, mock_settings):
        mock_settings.reserve_threshold = Decimal("100000.00")
        assert check_reserve_threshold(Decimal("0.00")) is False


# ---------------------------------------------------------------------------
# calculate_round_payouts
# ---------------------------------------------------------------------------

def _make_bet(color: str, amount: str, odds: str, player_id=None, bet_id=None):
    """Helper to create a mock Bet object."""
    bet = MagicMock()
    bet.id = bet_id or uuid4()
    bet.player_id = player_id or uuid4()
    bet.color = color
    bet.amount = Decimal(amount)
    bet.odds_at_placement = Decimal(odds)
    bet.is_winner = None
    return bet


class TestCalculateRoundPayouts:
    """Tests for round-level payout computation."""

    @pytest.mark.asyncio
    async def test_winner_gets_correct_payout(self):
        round_id = uuid4()
        bet = _make_bet("red", "100.00", "2.00")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [bet]

        session = AsyncMock()
        session.execute.return_value = mock_result

        odds = {"red": 2.0, "green": 3.0, "blue": 5.0}
        # winning_number=2 → red wins; payout = 100 × 0.98 × 2.0 = 196.00
        payouts = await calculate_round_payouts(session, round_id, "red", odds, winning_number=2)

        assert len(payouts) == 1
        assert payouts[0].is_winner is True
        assert payouts[0].amount == Decimal("196.00")
        assert bet.is_winner is True

    @pytest.mark.asyncio
    async def test_loser_gets_zero_payout(self):
        round_id = uuid4()
        bet = _make_bet("green", "50.00", "3.00")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [bet]

        session = AsyncMock()
        session.execute.return_value = mock_result

        odds = {"red": 2.0, "green": 3.0, "blue": 5.0}
        payouts = await calculate_round_payouts(session, round_id, "red", odds)

        assert len(payouts) == 1
        assert payouts[0].is_winner is False
        assert payouts[0].amount == Decimal("0.00")
        assert bet.is_winner is False

    @pytest.mark.asyncio
    async def test_mixed_winners_and_losers(self):
        round_id = uuid4()
        winner = _make_bet("red", "100.00", "2.00")
        loser = _make_bet("blue", "75.00", "5.00")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [winner, loser]

        session = AsyncMock()
        session.execute.return_value = mock_result

        odds = {"red": 2.0, "green": 3.0, "blue": 5.0}
        payouts = await calculate_round_payouts(session, round_id, "red", odds)

        assert len(payouts) == 2
        winner_payout = next(p for p in payouts if p.is_winner)
        loser_payout = next(p for p in payouts if not p.is_winner)
        assert winner_payout.amount == Decimal("196.00")  # 100 × 0.98 × 2.0
        assert loser_payout.amount == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_no_bets_returns_empty(self):
        round_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        session = AsyncMock()
        session.execute.return_value = mock_result

        payouts = await calculate_round_payouts(session, round_id, "red", {"red": 2.0})
        assert payouts == []

    @pytest.mark.asyncio
    async def test_odds_converted_from_float_to_decimal(self):
        """Odds dict comes from JSON (float values) but calculation must use Decimal."""
        round_id = uuid4()
        bet = _make_bet("red", "33.33", "2.50")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [bet]

        session = AsyncMock()
        session.execute.return_value = mock_result

        # Float odds from JSON — the service must convert via Decimal(str(...))
        odds = {"red": 2.5}
        payouts = await calculate_round_payouts(session, round_id, "red", odds)

        # 33.33 × 0.98 × 2.5 = 81.6585, quantized to 81.66
        expected = (Decimal("33.33") * Decimal("0.98") * Decimal("2.5")).quantize(Decimal("0.01"))
        assert payouts[0].amount == expected

    @pytest.mark.asyncio
    async def test_payout_result_fields(self):
        round_id = uuid4()
        player_id = uuid4()
        bet_id = uuid4()
        bet = _make_bet("red", "10.00", "2.00", player_id=player_id, bet_id=bet_id)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [bet]

        session = AsyncMock()
        session.execute.return_value = mock_result

        payouts = await calculate_round_payouts(session, round_id, "red", {"red": 2.0})

        pr = payouts[0]
        assert pr.bet_id == bet_id
        assert pr.player_id == player_id
        assert isinstance(pr, PayoutResult)


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestIsNumberBet:
    """Tests for _is_number_bet helper."""

    def test_digit_strings_are_number_bets(self):
        for d in "0123456789":
            assert _is_number_bet(d) is True

    def test_color_names_are_not_number_bets(self):
        for c in ("green", "red", "violet"):
            assert _is_number_bet(c) is False

    def test_multi_digit_strings_are_not_number_bets(self):
        assert _is_number_bet("10") is False
        assert _is_number_bet("99") is False


class TestIsColorWinner:
    """Tests for _is_color_winner helper."""

    def test_green_wins_on_green_numbers(self):
        for n in (0, 1, 3, 5, 7, 9):
            assert _is_color_winner("green", n) is True

    def test_green_loses_on_red_numbers(self):
        for n in (2, 4, 6, 8):
            assert _is_color_winner("green", n) is False

    def test_red_wins_on_red_numbers(self):
        for n in (2, 4, 6, 8):
            assert _is_color_winner("red", n) is True

    def test_red_loses_on_green_numbers(self):
        for n in (0, 1, 3, 5, 7, 9):
            assert _is_color_winner("red", n) is False

    def test_violet_wins_on_0_and_5(self):
        assert _is_color_winner("violet", 0) is True
        assert _is_color_winner("violet", 5) is True

    def test_violet_loses_on_other_numbers(self):
        for n in (1, 2, 3, 4, 6, 7, 8, 9):
            assert _is_color_winner("violet", n) is False


# ---------------------------------------------------------------------------
# Number bet payouts
# ---------------------------------------------------------------------------

class TestNumberBetPayouts:
    """Tests for number bet payout logic in calculate_round_payouts."""

    @pytest.mark.asyncio
    async def test_number_bet_winner(self):
        round_id = uuid4()
        bet = _make_bet("3", "100.00", "9.60")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [bet]

        session = AsyncMock()
        session.execute.return_value = mock_result

        odds = {"green": 2.0, "red": 2.0, "violet": 4.8, "number": 9.6}
        payouts = await calculate_round_payouts(
            session, round_id, "green", odds, winning_number=3
        )

        assert len(payouts) == 1
        assert payouts[0].is_winner is True
        # 100 × 0.98 × 9.6 = 940.80
        assert payouts[0].amount == Decimal("940.80")

    @pytest.mark.asyncio
    async def test_number_bet_loser(self):
        round_id = uuid4()
        bet = _make_bet("7", "50.00", "9.60")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [bet]

        session = AsyncMock()
        session.execute.return_value = mock_result

        odds = {"green": 2.0, "red": 2.0, "violet": 4.8, "number": 9.6}
        payouts = await calculate_round_payouts(
            session, round_id, "green", odds, winning_number=3
        )

        assert len(payouts) == 1
        assert payouts[0].is_winner is False
        assert payouts[0].amount == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_number_bet_quantized_to_2dp(self):
        round_id = uuid4()
        bet = _make_bet("5", "33.33", "9.60")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [bet]

        session = AsyncMock()
        session.execute.return_value = mock_result

        odds = {"green": 2.0, "violet": 4.8, "number": 9.6}
        payouts = await calculate_round_payouts(
            session, round_id, "violet", odds, winning_number=5
        )

        # 33.33 × 0.98 × 9.6 = 313.5648..., quantized to 313.56
        expected = (Decimal("33.33") * Decimal("0.98") * Decimal("9.6")).quantize(Decimal("0.01"))
        assert payouts[0].amount == expected


# ---------------------------------------------------------------------------
# Dual-color number payouts (0 and 5)
# ---------------------------------------------------------------------------

class TestDualColorPayouts:
    """Tests for dual-color numbers 0 and 5 where both green and violet win."""

    @pytest.mark.asyncio
    async def test_green_and_violet_both_win_on_number_0(self):
        round_id = uuid4()
        green_bet = _make_bet("green", "100.00", "2.00")
        violet_bet = _make_bet("violet", "100.00", "4.80")
        red_bet = _make_bet("red", "100.00", "2.00")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [green_bet, violet_bet, red_bet]

        session = AsyncMock()
        session.execute.return_value = mock_result

        odds = {"green": 2.0, "red": 2.0, "violet": 4.8, "number": 9.6}
        payouts = await calculate_round_payouts(
            session, round_id, "violet", odds, winning_number=0
        )

        assert len(payouts) == 3
        green_payout = next(p for p in payouts if p.bet_id == green_bet.id)
        violet_payout = next(p for p in payouts if p.bet_id == violet_bet.id)
        red_payout = next(p for p in payouts if p.bet_id == red_bet.id)

        assert green_payout.is_winner is True
        assert green_payout.amount == Decimal("196.00")  # 100 × 0.98 × 2.0
        assert violet_payout.is_winner is True
        assert violet_payout.amount == Decimal("470.40")  # 100 × 0.98 × 4.8
        assert red_payout.is_winner is False
        assert red_payout.amount == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_green_and_violet_both_win_on_number_5(self):
        round_id = uuid4()
        green_bet = _make_bet("green", "50.00", "2.00")
        violet_bet = _make_bet("violet", "50.00", "4.80")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [green_bet, violet_bet]

        session = AsyncMock()
        session.execute.return_value = mock_result

        odds = {"green": 2.0, "red": 2.0, "violet": 4.8, "number": 9.6}
        payouts = await calculate_round_payouts(
            session, round_id, "violet", odds, winning_number=5
        )

        green_payout = next(p for p in payouts if p.bet_id == green_bet.id)
        violet_payout = next(p for p in payouts if p.bet_id == violet_bet.id)

        assert green_payout.is_winner is True
        assert green_payout.amount == Decimal("98.00")  # 50 × 0.98 × 2.0
        assert violet_payout.is_winner is True
        assert violet_payout.amount == Decimal("235.20")  # 50 × 0.98 × 4.8

    @pytest.mark.asyncio
    async def test_number_and_color_bets_mixed_on_dual_number(self):
        """Number bet on 0, green color bet, and violet color bet all win on winning_number=0."""
        round_id = uuid4()
        number_bet = _make_bet("0", "100.00", "9.60")
        green_bet = _make_bet("green", "100.00", "2.00")
        violet_bet = _make_bet("violet", "100.00", "4.80")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [number_bet, green_bet, violet_bet]

        session = AsyncMock()
        session.execute.return_value = mock_result

        odds = {"green": 2.0, "red": 2.0, "violet": 4.8, "number": 9.6}
        payouts = await calculate_round_payouts(
            session, round_id, "violet", odds, winning_number=0
        )

        num_payout = next(p for p in payouts if p.bet_id == number_bet.id)
        grn_payout = next(p for p in payouts if p.bet_id == green_bet.id)
        vio_payout = next(p for p in payouts if p.bet_id == violet_bet.id)

        assert num_payout.is_winner is True
        assert num_payout.amount == Decimal("940.80")  # 100 × 0.98 × 9.6
        assert grn_payout.is_winner is True
        assert grn_payout.amount == Decimal("196.00")  # 100 × 0.98 × 2.0
        assert vio_payout.is_winner is True
        assert vio_payout.amount == Decimal("470.40")  # 100 × 0.98 × 4.8


# ---------------------------------------------------------------------------
# _is_big_small_bet helper tests
# ---------------------------------------------------------------------------

class TestIsBigSmallBet:
    """Tests for _is_big_small_bet helper.

    Validates: Requirements 1.1, 1.2
    """

    def test_big_is_big_small_bet(self):
        assert _is_big_small_bet("big") is True

    def test_small_is_big_small_bet(self):
        assert _is_big_small_bet("small") is True

    def test_color_names_are_not_big_small(self):
        for c in ("green", "red", "violet"):
            assert _is_big_small_bet(c) is False

    def test_digit_strings_are_not_big_small(self):
        for d in "0123456789":
            assert _is_big_small_bet(d) is False

    def test_empty_string_is_not_big_small(self):
        assert _is_big_small_bet("") is False


# ---------------------------------------------------------------------------
# _is_big_small_winner helper tests
# ---------------------------------------------------------------------------

class TestIsBigSmallWinner:
    """Tests for _is_big_small_winner helper covering all numbers 0–9.

    Validates: Requirements 1.3, 1.4, 1.5, 1.6
    """

    @pytest.mark.parametrize("number", [5, 6, 7, 8, 9])
    def test_big_wins_on_big_numbers(self, number):
        """Big bet wins when winning number is 5, 6, 7, 8, or 9."""
        assert _is_big_small_winner("big", number) is True

    @pytest.mark.parametrize("number", [0, 1, 2, 3, 4])
    def test_big_loses_on_small_numbers(self, number):
        """Big bet loses when winning number is 0, 1, 2, 3, or 4."""
        assert _is_big_small_winner("big", number) is False

    @pytest.mark.parametrize("number", [0, 1, 2, 3, 4])
    def test_small_wins_on_small_numbers(self, number):
        """Small bet wins when winning number is 0, 1, 2, 3, or 4."""
        assert _is_big_small_winner("small", number) is True

    @pytest.mark.parametrize("number", [5, 6, 7, 8, 9])
    def test_small_loses_on_big_numbers(self, number):
        """Small bet loses when winning number is 5, 6, 7, 8, or 9."""
        assert _is_big_small_winner("small", number) is False

    def test_invalid_bet_type_returns_false(self):
        """Non big/small bet type always returns False."""
        assert _is_big_small_winner("medium", 5) is False
        assert _is_big_small_winner("red", 3) is False


# ---------------------------------------------------------------------------
# Big/Small bet payouts in calculate_round_payouts
# ---------------------------------------------------------------------------

class TestBigSmallPayouts:
    """Tests for big/small bet payout logic in calculate_round_payouts.

    Validates: Requirements 1.3, 1.4, 1.5, 1.6, 2.1, 2.2
    """

    @pytest.mark.asyncio
    async def test_big_bet_wins_on_big_number(self):
        """Big bet wins when winning_number is 7 (in {5,6,7,8,9})."""
        round_id = uuid4()
        bet = _make_bet("big", "100.00", "2.00")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [bet]

        session = AsyncMock()
        session.execute.return_value = mock_result

        odds = {"green": 2.0, "red": 2.0, "violet": 4.8, "number": 9.6, "big": 2.0, "small": 2.0}
        payouts = await calculate_round_payouts(
            session, round_id, "green", odds, winning_number=7
        )

        assert len(payouts) == 1
        assert payouts[0].is_winner is True
        # 100 × 0.98 × 2.0 = 196.00
        assert payouts[0].amount == Decimal("196.00")

    @pytest.mark.asyncio
    async def test_big_bet_loses_on_small_number(self):
        """Big bet loses when winning_number is 2 (in {0,1,2,3,4})."""
        round_id = uuid4()
        bet = _make_bet("big", "100.00", "2.00")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [bet]

        session = AsyncMock()
        session.execute.return_value = mock_result

        odds = {"green": 2.0, "red": 2.0, "violet": 4.8, "number": 9.6, "big": 2.0, "small": 2.0}
        payouts = await calculate_round_payouts(
            session, round_id, "red", odds, winning_number=2
        )

        assert len(payouts) == 1
        assert payouts[0].is_winner is False
        assert payouts[0].amount == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_small_bet_wins_on_small_number(self):
        """Small bet wins when winning_number is 3 (in {0,1,2,3,4})."""
        round_id = uuid4()
        bet = _make_bet("small", "50.00", "2.00")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [bet]

        session = AsyncMock()
        session.execute.return_value = mock_result

        odds = {"green": 2.0, "red": 2.0, "violet": 4.8, "number": 9.6, "big": 2.0, "small": 2.0}
        payouts = await calculate_round_payouts(
            session, round_id, "green", odds, winning_number=3
        )

        assert len(payouts) == 1
        assert payouts[0].is_winner is True
        # 50 × 0.98 × 2.0 = 98.00
        assert payouts[0].amount == Decimal("98.00")

    @pytest.mark.asyncio
    async def test_small_bet_loses_on_big_number(self):
        """Small bet loses when winning_number is 8 (in {5,6,7,8,9})."""
        round_id = uuid4()
        bet = _make_bet("small", "50.00", "2.00")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [bet]

        session = AsyncMock()
        session.execute.return_value = mock_result

        odds = {"green": 2.0, "red": 2.0, "violet": 4.8, "number": 9.6, "big": 2.0, "small": 2.0}
        payouts = await calculate_round_payouts(
            session, round_id, "red", odds, winning_number=8
        )

        assert len(payouts) == 1
        assert payouts[0].is_winner is False
        assert payouts[0].amount == Decimal("0.00")


# ---------------------------------------------------------------------------
# Mixed bet types in calculate_round_payouts
# ---------------------------------------------------------------------------

class TestMixedBetTypePayouts:
    """Tests for calculate_round_payouts with all bet types mixed together.

    Validates: Requirements 1.1–1.7, 2.1–2.4
    """

    @pytest.mark.asyncio
    async def test_color_number_big_small_mixed_on_big_green_number(self):
        """Winning number 7 (green, big): green wins, big wins, number 7 wins,
        red loses, small loses, number 3 loses."""
        round_id = uuid4()
        green_bet = _make_bet("green", "100.00", "2.00")
        red_bet = _make_bet("red", "100.00", "2.00")
        number_7_bet = _make_bet("7", "100.00", "9.60")
        number_3_bet = _make_bet("3", "100.00", "9.60")
        big_bet = _make_bet("big", "100.00", "2.00")
        small_bet = _make_bet("small", "100.00", "2.00")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            green_bet, red_bet, number_7_bet, number_3_bet, big_bet, small_bet
        ]

        session = AsyncMock()
        session.execute.return_value = mock_result

        odds = {"green": 2.0, "red": 2.0, "violet": 4.8, "number": 9.6, "big": 2.0, "small": 2.0}
        payouts = await calculate_round_payouts(
            session, round_id, "green", odds, winning_number=7
        )

        assert len(payouts) == 6

        green_p = next(p for p in payouts if p.bet_id == green_bet.id)
        red_p = next(p for p in payouts if p.bet_id == red_bet.id)
        num7_p = next(p for p in payouts if p.bet_id == number_7_bet.id)
        num3_p = next(p for p in payouts if p.bet_id == number_3_bet.id)
        big_p = next(p for p in payouts if p.bet_id == big_bet.id)
        small_p = next(p for p in payouts if p.bet_id == small_bet.id)

        # Green wins (7 is green)
        assert green_p.is_winner is True
        assert green_p.amount == Decimal("196.00")  # 100 × 0.98 × 2.0

        # Red loses (7 is not red)
        assert red_p.is_winner is False
        assert red_p.amount == Decimal("0.00")

        # Number 7 wins
        assert num7_p.is_winner is True
        assert num7_p.amount == Decimal("940.80")  # 100 × 0.98 × 9.6

        # Number 3 loses
        assert num3_p.is_winner is False
        assert num3_p.amount == Decimal("0.00")

        # Big wins (7 >= 5)
        assert big_p.is_winner is True
        assert big_p.amount == Decimal("196.00")  # 100 × 0.98 × 2.0

        # Small loses (7 >= 5)
        assert small_p.is_winner is False
        assert small_p.amount == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_color_number_big_small_mixed_on_small_red_number(self):
        """Winning number 2 (red, small): red wins, small wins, number 2 wins,
        green loses, big loses, number 5 loses."""
        round_id = uuid4()
        green_bet = _make_bet("green", "80.00", "2.00")
        red_bet = _make_bet("red", "80.00", "2.00")
        number_2_bet = _make_bet("2", "80.00", "9.60")
        number_5_bet = _make_bet("5", "80.00", "9.60")
        big_bet = _make_bet("big", "80.00", "2.00")
        small_bet = _make_bet("small", "80.00", "2.00")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            green_bet, red_bet, number_2_bet, number_5_bet, big_bet, small_bet
        ]

        session = AsyncMock()
        session.execute.return_value = mock_result

        odds = {"green": 2.0, "red": 2.0, "violet": 4.8, "number": 9.6, "big": 2.0, "small": 2.0}
        payouts = await calculate_round_payouts(
            session, round_id, "red", odds, winning_number=2
        )

        assert len(payouts) == 6

        green_p = next(p for p in payouts if p.bet_id == green_bet.id)
        red_p = next(p for p in payouts if p.bet_id == red_bet.id)
        num2_p = next(p for p in payouts if p.bet_id == number_2_bet.id)
        num5_p = next(p for p in payouts if p.bet_id == number_5_bet.id)
        big_p = next(p for p in payouts if p.bet_id == big_bet.id)
        small_p = next(p for p in payouts if p.bet_id == small_bet.id)

        # Green loses (2 is not green)
        assert green_p.is_winner is False
        assert green_p.amount == Decimal("0.00")

        # Red wins (2 is red)
        assert red_p.is_winner is True
        assert red_p.amount == Decimal("156.80")  # 80 × 0.98 × 2.0

        # Number 2 wins
        assert num2_p.is_winner is True
        assert num2_p.amount == Decimal("752.64")  # 80 × 0.98 × 9.6

        # Number 5 loses
        assert num5_p.is_winner is False
        assert num5_p.amount == Decimal("0.00")

        # Big loses (2 < 5)
        assert big_p.is_winner is False
        assert big_p.amount == Decimal("0.00")

        # Small wins (2 <= 4)
        assert small_p.is_winner is True
        assert small_p.amount == Decimal("156.80")  # 80 × 0.98 × 2.0
