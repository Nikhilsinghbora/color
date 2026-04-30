"""Unit tests for the game engine service."""

from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import (
    BetLimitError,
    BettingClosedError,
    InsufficientBalanceError,
    InvalidTransitionError,
)
from app.models.game import Bet, GameMode, GameRound, Payout, RoundPhase
from app.models.rng import RNGAuditLog
from app.models.player import Player, Wallet
from app.services import game_engine


class TestStartRound:
    """Tests for start_round."""

    async def test_creates_round_in_betting_phase(self, session, game_mode):
        game_round = await game_engine.start_round(session, game_mode.id)
        assert game_round.phase == RoundPhase.BETTING
        assert game_round.game_mode_id == game_mode.id

    async def test_sets_betting_ends_at(self, session, game_mode):
        game_round = await game_engine.start_round(session, game_mode.id)
        assert game_round.betting_ends_at is not None

    async def test_initializes_totals_to_zero(self, session, game_mode):
        game_round = await game_engine.start_round(session, game_mode.id)
        assert game_round.total_bets == Decimal("0.00")
        assert game_round.total_payouts == Decimal("0.00")

    async def test_not_flagged_for_review(self, session, game_mode):
        game_round = await game_engine.start_round(session, game_mode.id)
        assert game_round.flagged_for_review is False


class TestPlaceBet:
    """Tests for place_bet."""

    async def test_valid_bet_succeeds(
        self, session, game_mode, player_with_wallet, betting_round
    ):
        player, wallet = player_with_wallet
        bet = await game_engine.place_bet(
            session, player.id, betting_round.id, "red", Decimal("10.00")
        )
        assert bet.color == "red"
        assert bet.amount == Decimal("10.00")
        assert bet.player_id == player.id
        assert bet.round_id == betting_round.id

    async def test_deducts_from_wallet(
        self, session, game_mode, player_with_wallet, betting_round
    ):
        player, wallet = player_with_wallet
        initial_balance = wallet.balance
        await game_engine.place_bet(
            session, player.id, betting_round.id, "red", Decimal("50.00")
        )
        await session.refresh(wallet)
        assert wallet.balance == initial_balance - Decimal("50.00")

    async def test_rejects_bet_below_min(
        self, session, game_mode, player_with_wallet, betting_round
    ):
        player, _ = player_with_wallet
        with pytest.raises(BetLimitError):
            await game_engine.place_bet(
                session, player.id, betting_round.id, "red", Decimal("0.50")
            )

    async def test_rejects_bet_above_max(
        self, session, game_mode, player_with_wallet, betting_round
    ):
        player, _ = player_with_wallet
        with pytest.raises(BetLimitError):
            await game_engine.place_bet(
                session, player.id, betting_round.id, "red", Decimal("5000.00")
            )

    async def test_rejects_bet_exceeding_balance(
        self, session, game_mode, player_with_wallet, betting_round
    ):
        player, wallet = player_with_wallet
        with pytest.raises(InsufficientBalanceError):
            await game_engine.place_bet(
                session, player.id, betting_round.id, "red", Decimal("999.00")
            )

    async def test_rejects_bet_outside_betting_phase(
        self, session, game_mode, player_with_wallet, betting_round
    ):
        player, _ = player_with_wallet
        # Move to RESOLUTION phase
        await game_engine.resolve_round(session, betting_round.id)
        with pytest.raises(BettingClosedError):
            await game_engine.place_bet(
                session, player.id, betting_round.id, "red", Decimal("10.00")
            )

    async def test_multiple_bets_different_colors(
        self, session, game_mode, player_with_wallet, betting_round
    ):
        player, _ = player_with_wallet
        bet1 = await game_engine.place_bet(
            session, player.id, betting_round.id, "red", Decimal("10.00")
        )
        bet2 = await game_engine.place_bet(
            session, player.id, betting_round.id, "green", Decimal("20.00")
        )
        assert bet1.color == "red"
        assert bet2.color == "green"

    async def test_records_odds_at_placement(
        self, session, game_mode, player_with_wallet, betting_round
    ):
        player, _ = player_with_wallet
        bet = await game_engine.place_bet(
            session, player.id, betting_round.id, "red", Decimal("10.00")
        )
        assert bet.odds_at_placement == Decimal("2.00")

    async def test_updates_round_total_bets(
        self, session, game_mode, player_with_wallet, betting_round
    ):
        player, _ = player_with_wallet
        await game_engine.place_bet(
            session, player.id, betting_round.id, "red", Decimal("25.00")
        )
        await session.refresh(betting_round)
        assert betting_round.total_bets == Decimal("25.00")


class TestPlaceBetNumberBets:
    """Tests for place_bet with number bets (digit strings '0'-'9')."""

    @pytest_asyncio.fixture
    async def number_game_mode(self, session: AsyncSession) -> GameMode:
        """Game mode with number odds included."""
        mode = GameMode(
            id=uuid4(),
            name="NumberMode",
            mode_type="classic",
            color_options=["red", "green", "violet"],
            odds={"red": 2.0, "green": 2.0, "violet": 4.8, "number": 9.6, "big": 2.0, "small": 2.0},
            min_bet=Decimal("1.00"),
            max_bet=Decimal("1000.00"),
            round_duration_seconds=30,
        )
        session.add(mode)
        await session.flush()
        return mode

    @pytest_asyncio.fixture
    async def number_betting_round(self, session: AsyncSession, number_game_mode: GameMode) -> GameRound:
        game_round = await game_engine.start_round(session, number_game_mode.id)
        return game_round

    async def test_accepts_digit_string_bet(
        self, session, number_game_mode, player_with_wallet, number_betting_round
    ):
        player, _ = player_with_wallet
        bet = await game_engine.place_bet(
            session, player.id, number_betting_round.id, "5", Decimal("10.00")
        )
        assert bet.color == "5"
        assert bet.amount == Decimal("10.00")

    async def test_number_bet_uses_number_odds(
        self, session, number_game_mode, player_with_wallet, number_betting_round
    ):
        player, _ = player_with_wallet
        bet = await game_engine.place_bet(
            session, player.id, number_betting_round.id, "3", Decimal("10.00")
        )
        assert bet.odds_at_placement == Decimal("9.60")

    async def test_color_bet_still_uses_color_odds(
        self, session, number_game_mode, player_with_wallet, number_betting_round
    ):
        player, _ = player_with_wallet
        bet = await game_engine.place_bet(
            session, player.id, number_betting_round.id, "red", Decimal("10.00")
        )
        assert bet.odds_at_placement == Decimal("2.00")

    async def test_all_digits_accepted(
        self, session, number_game_mode, player_with_wallet, number_betting_round
    ):
        player, _ = player_with_wallet
        for digit in range(10):
            bet = await game_engine.place_bet(
                session, player.id, number_betting_round.id, str(digit), Decimal("1.00")
            )
            assert bet.color == str(digit)

    async def test_rejects_invalid_string(
        self, session, number_game_mode, player_with_wallet, number_betting_round
    ):
        player, _ = player_with_wallet
        with pytest.raises(ValueError):
            await game_engine.place_bet(
                session, player.id, number_betting_round.id, "abc", Decimal("10.00")
            )

    async def test_rejects_multi_digit_string(
        self, session, number_game_mode, player_with_wallet, number_betting_round
    ):
        player, _ = player_with_wallet
        with pytest.raises(ValueError):
            await game_engine.place_bet(
                session, player.id, number_betting_round.id, "10", Decimal("10.00")
            )


class TestResolveRound:
    """Tests for resolve_round."""

    async def test_transitions_to_resolution(self, session, game_mode, betting_round):
        resolved = await game_engine.resolve_round(session, betting_round.id)
        assert resolved.phase == RoundPhase.RESOLUTION

    async def test_sets_winning_color(self, session, game_mode, betting_round):
        resolved = await game_engine.resolve_round(session, betting_round.id)
        assert resolved.winning_color in ["red", "green", "violet"]

    async def test_sets_resolved_at(self, session, game_mode, betting_round):
        resolved = await game_engine.resolve_round(session, betting_round.id)
        assert resolved.resolved_at is not None

    async def test_rejects_resolve_from_resolution(self, session, game_mode, betting_round):
        await game_engine.resolve_round(session, betting_round.id)
        with pytest.raises(InvalidTransitionError):
            await game_engine.resolve_round(session, betting_round.id)

    async def test_rejects_resolve_from_result(self, session, game_mode, betting_round):
        await game_engine.resolve_round(session, betting_round.id)
        await game_engine.finalize_round(session, betting_round.id)
        with pytest.raises(InvalidTransitionError):
            await game_engine.resolve_round(session, betting_round.id)


class TestFinalizeRound:
    """Tests for finalize_round."""

    async def test_transitions_to_result(self, session, game_mode, betting_round):
        await game_engine.resolve_round(session, betting_round.id)
        finalized = await game_engine.finalize_round(session, betting_round.id)
        assert finalized.phase == RoundPhase.RESULT

    async def test_sets_completed_at(self, session, game_mode, betting_round):
        await game_engine.resolve_round(session, betting_round.id)
        finalized = await game_engine.finalize_round(session, betting_round.id)
        assert finalized.completed_at is not None

    async def test_rejects_finalize_from_betting(self, session, game_mode, betting_round):
        with pytest.raises(InvalidTransitionError):
            await game_engine.finalize_round(session, betting_round.id)

    async def test_credits_winners(
        self, session, game_mode, player_with_wallet, betting_round
    ):
        player, wallet = player_with_wallet
        initial_balance = wallet.balance

        # Place bets on red and green to guarantee a winner
        # (RNG winning colors are derived from NUMBER_COLOR_MAP: green, red, or violet)
        # Green wins on numbers {0,1,3,5,7,9}, Red wins on {2,4,6,8}
        await game_engine.place_bet(
            session, player.id, betting_round.id, "red", Decimal("10.00")
        )
        await game_engine.place_bet(
            session, player.id, betting_round.id, "green", Decimal("10.00")
        )

        resolved = await game_engine.resolve_round(session, betting_round.id)

        finalized = await game_engine.finalize_round(session, betting_round.id)

        # Player should have been credited for the winning bet
        await session.refresh(wallet)
        # Balance should be greater than initial - total bets (20.00)
        # because one of the bets won and was credited back with odds
        assert wallet.balance > initial_balance - Decimal("20.00")
        # But should not exceed initial balance (payout is adjusted by profit management)
        # At minimum, the winner gets some payout
        assert finalized.total_payouts > Decimal("0.00")

    async def test_total_payouts_updated(
        self, session, game_mode, player_with_wallet, betting_round
    ):
        player, _ = player_with_wallet
        await game_engine.place_bet(
            session, player.id, betting_round.id, "red", Decimal("10.00")
        )
        await game_engine.resolve_round(session, betting_round.id)
        finalized = await game_engine.finalize_round(session, betting_round.id)
        # total_payouts should be >= 0
        assert finalized.total_payouts >= Decimal("0.00")


class TestGetRoundState:
    """Tests for get_round_state."""

    async def test_returns_round_state(self, session, game_mode, betting_round):
        state = await game_engine.get_round_state(session, betting_round.id)
        assert state.round_id == betting_round.id
        assert state.phase == RoundPhase.BETTING
        assert state.game_mode_id == game_mode.id

    async def test_reflects_phase_changes(self, session, game_mode, betting_round):
        await game_engine.resolve_round(session, betting_round.id)
        state = await game_engine.get_round_state(session, betting_round.id)
        assert state.phase == RoundPhase.RESOLUTION

    async def test_includes_period_number(self, session, game_mode, betting_round):
        """Validates: Requirements 5.4, 15.5"""
        state = await game_engine.get_round_state(session, betting_round.id)
        assert state.period_number is not None
        assert state.period_number == betting_round.period_number


class TestStateMachineTransitions:
    """Tests for invalid state transitions."""

    async def test_betting_to_result_invalid(self, session, game_mode, betting_round):
        """Cannot skip RESOLUTION and go directly to RESULT."""
        with pytest.raises(InvalidTransitionError):
            await game_engine.finalize_round(session, betting_round.id)

    async def test_result_to_betting_invalid(self, session, game_mode, betting_round):
        """Cannot go back from RESULT to BETTING."""
        await game_engine.resolve_round(session, betting_round.id)
        await game_engine.finalize_round(session, betting_round.id)
        # Trying to resolve again should fail
        with pytest.raises(InvalidTransitionError):
            await game_engine.resolve_round(session, betting_round.id)

    async def test_result_to_resolution_invalid(self, session, game_mode, betting_round):
        """Cannot go from RESULT back to RESOLUTION."""
        await game_engine.resolve_round(session, betting_round.id)
        await game_engine.finalize_round(session, betting_round.id)
        with pytest.raises(InvalidTransitionError):
            await game_engine.finalize_round(session, betting_round.id)


class TestFullRoundLifecycle:
    """Test the complete round lifecycle: BETTING → RESOLUTION → RESULT → new round."""

    async def test_full_lifecycle_transitions(self, session, game_mode):
        """Validates: Requirements 3.1, 3.4, 3.5, 3.6"""
        # Start round → BETTING
        round1 = await game_engine.start_round(session, game_mode.id)
        assert round1.phase == RoundPhase.BETTING

        # Resolve → RESOLUTION
        resolved = await game_engine.resolve_round(session, round1.id)
        assert resolved.phase == RoundPhase.RESOLUTION
        assert resolved.winning_color is not None

        # Finalize → RESULT
        finalized = await game_engine.finalize_round(session, round1.id)
        assert finalized.phase == RoundPhase.RESULT
        assert finalized.completed_at is not None

        # Start a new round after the previous one completes
        round2 = await game_engine.start_round(session, game_mode.id)
        assert round2.phase == RoundPhase.BETTING
        assert round2.id != round1.id
        assert round2.game_mode_id == game_mode.id


class TestRNGInvocationDuringResolution:
    """Test that resolve_round invokes the RNG engine and creates an audit log entry."""

    async def test_rng_audit_log_created_on_resolve(self, session, game_mode, betting_round):
        """Validates: Requirements 3.4, 5.3"""
        from app.services.rng_engine import NUMBER_COLOR_MAP

        await game_engine.resolve_round(session, betting_round.id)

        result = await session.execute(
            select(RNGAuditLog).where(RNGAuditLog.round_id == betting_round.id)
        )
        audit = result.scalar_one()

        assert audit.algorithm == "secrets.randbelow"
        assert isinstance(audit.raw_value, int)
        assert 0 <= audit.raw_value <= 9
        assert audit.num_options == 10
        assert audit.selected_color in ("green", "red", "violet")
        assert audit.selected_color == NUMBER_COLOR_MAP[audit.raw_value]


class TestPlaceBetBigSmall:
    """Tests for place_bet with big/small bet types.

    Validates: Requirements 1.1, 1.2, 1.7
    """

    async def test_accepts_big_bet(
        self, session, game_mode, player_with_wallet, betting_round
    ):
        """Validates: Requirements 1.1"""
        player, _ = player_with_wallet
        bet = await game_engine.place_bet(
            session, player.id, betting_round.id, "big", Decimal("10.00")
        )
        assert bet.color == "big"
        assert bet.amount == Decimal("10.00")

    async def test_accepts_small_bet(
        self, session, game_mode, player_with_wallet, betting_round
    ):
        """Validates: Requirements 1.2"""
        player, _ = player_with_wallet
        bet = await game_engine.place_bet(
            session, player.id, betting_round.id, "small", Decimal("10.00")
        )
        assert bet.color == "small"
        assert bet.amount == Decimal("10.00")

    async def test_big_bet_uses_big_odds(
        self, session, game_mode, player_with_wallet, betting_round
    ):
        """Validates: Requirements 1.1"""
        player, _ = player_with_wallet
        bet = await game_engine.place_bet(
            session, player.id, betting_round.id, "big", Decimal("10.00")
        )
        assert bet.odds_at_placement == Decimal("2.00")

    async def test_small_bet_uses_small_odds(
        self, session, game_mode, player_with_wallet, betting_round
    ):
        """Validates: Requirements 1.2"""
        player, _ = player_with_wallet
        bet = await game_engine.place_bet(
            session, player.id, betting_round.id, "small", Decimal("10.00")
        )
        assert bet.odds_at_placement == Decimal("2.00")

    async def test_rejects_invalid_bet_type(
        self, session, game_mode, player_with_wallet, betting_round
    ):
        """Validates: Requirements 1.7"""
        player, _ = player_with_wallet
        with pytest.raises(ValueError, match="Invalid bet choice"):
            await game_engine.place_bet(
                session, player.id, betting_round.id, "medium", Decimal("10.00")
            )

    async def test_rejects_empty_string_bet(
        self, session, game_mode, player_with_wallet, betting_round
    ):
        """Validates: Requirements 1.7"""
        player, _ = player_with_wallet
        with pytest.raises(ValueError, match="Invalid bet choice"):
            await game_engine.place_bet(
                session, player.id, betting_round.id, "", Decimal("10.00")
            )

    async def test_big_bet_deducts_from_wallet(
        self, session, game_mode, player_with_wallet, betting_round
    ):
        player, wallet = player_with_wallet
        initial_balance = wallet.balance
        await game_engine.place_bet(
            session, player.id, betting_round.id, "big", Decimal("25.00")
        )
        await session.refresh(wallet)
        assert wallet.balance == initial_balance - Decimal("25.00")

    async def test_big_and_small_bets_in_same_round(
        self, session, game_mode, player_with_wallet, betting_round
    ):
        player, _ = player_with_wallet
        bet1 = await game_engine.place_bet(
            session, player.id, betting_round.id, "big", Decimal("10.00")
        )
        bet2 = await game_engine.place_bet(
            session, player.id, betting_round.id, "small", Decimal("10.00")
        )
        assert bet1.color == "big"
        assert bet2.color == "small"

    async def test_big_small_updates_round_total_bets(
        self, session, game_mode, player_with_wallet, betting_round
    ):
        player, _ = player_with_wallet
        await game_engine.place_bet(
            session, player.id, betting_round.id, "big", Decimal("30.00")
        )
        await session.refresh(betting_round)
        assert betting_round.total_bets == Decimal("30.00")


class TestGetActiveRoundForMode:
    """Tests for get_active_round_for_mode()."""

    @pytest.mark.asyncio
    async def test_returns_betting_round(self, session, game_mode, betting_round):
        """Should return a round in BETTING phase."""
        result = await game_engine.get_active_round_for_mode(session, game_mode.id)
        assert result is not None
        assert result.id == betting_round.id
        assert result.phase == RoundPhase.BETTING

    @pytest.mark.asyncio
    async def test_returns_resolution_round(self, session, game_mode, betting_round):
        """Should return a round in RESOLUTION phase."""
        await game_engine.resolve_round(session, betting_round.id)
        result = await game_engine.get_active_round_for_mode(session, game_mode.id)
        assert result is not None
        assert result.id == betting_round.id
        assert result.phase == RoundPhase.RESOLUTION

    @pytest.mark.asyncio
    async def test_returns_none_when_no_active_round(self, session, game_mode):
        """Should return None when no BETTING or RESOLUTION round exists."""
        result = await game_engine.get_active_round_for_mode(session, game_mode.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_result_round(self, session, game_mode, betting_round):
        """Should not return a round in RESULT phase."""
        await game_engine.resolve_round(session, betting_round.id)
        await game_engine.finalize_round(session, betting_round.id)
        result = await game_engine.get_active_round_for_mode(session, game_mode.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_most_recent_active_round(self, session, game_mode):
        """When multiple active rounds exist, should return the most recent one."""
        from datetime import datetime, timedelta, timezone

        round1 = await game_engine.start_round(session, game_mode.id)
        round1.created_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        await session.flush()

        round2 = await game_engine.start_round(session, game_mode.id)
        round2.created_at = datetime(2025, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
        await session.flush()

        result = await game_engine.get_active_round_for_mode(session, game_mode.id)
        assert result is not None
        assert result.id == round2.id
