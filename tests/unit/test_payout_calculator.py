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
    PayoutResult,
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
        result = calculate_payout(Decimal("100.00"), Decimal("2.00"))
        assert result == Decimal("200.00")

    def test_quantizes_to_two_decimal_places(self):
        # 33.33 * 3 = 99.99 exactly, but 33.33 * 3.33 = 110.9889
        result = calculate_payout(Decimal("33.33"), Decimal("3.33"))
        assert result == Decimal("110.99")
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
        expected = (Decimal("99999.99") * Decimal("99.99")).quantize(Decimal("0.01"))
        assert result == expected

    def test_fractional_odds(self):
        result = calculate_payout(Decimal("10.00"), Decimal("1.50"))
        assert result == Decimal("15.00")

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
        # winning_number=2 → red wins
        payouts = await calculate_round_payouts(session, round_id, "red", odds, winning_number=2)

        assert len(payouts) == 1
        assert payouts[0].is_winner is True
        assert payouts[0].amount == Decimal("200.00")
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
        assert winner_payout.amount == Decimal("200.00")
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

        expected = (Decimal("33.33") * Decimal("2.5")).quantize(Decimal("0.01"))
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
        assert payouts[0].amount == Decimal("960.00")

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

        expected = (Decimal("33.33") * Decimal("9.6")).quantize(Decimal("0.01"))
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
        assert green_payout.amount == Decimal("200.00")
        assert violet_payout.is_winner is True
        assert violet_payout.amount == Decimal("480.00")
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
        assert green_payout.amount == Decimal("100.00")
        assert violet_payout.is_winner is True
        assert violet_payout.amount == Decimal("240.00")

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
        assert num_payout.amount == Decimal("960.00")
        assert grn_payout.is_winner is True
        assert grn_payout.amount == Decimal("200.00")
        assert vio_payout.is_winner is True
        assert vio_payout.amount == Decimal("480.00")
