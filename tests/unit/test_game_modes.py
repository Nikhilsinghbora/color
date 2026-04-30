"""Unit tests for game mode types and configuration.

Validates: Requirements 7.1, 7.2, 7.3
"""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.game_mode_service import create_game_mode


class TestClassicMode:
    """Tests for Classic game mode."""

    @pytest.mark.asyncio
    async def test_classic_mode_creation(self, session: AsyncSession):
        mode = await create_game_mode(
            session,
            name="Classic Standard",
            mode_type="classic",
            color_options=["red", "green", "blue"],
            odds={"red": 2.0, "green": 3.0, "blue": 5.0},
            min_bet=Decimal("1.00"),
            max_bet=Decimal("500.00"),
            round_duration_seconds=30,
        )
        assert mode.mode_type == "classic"
        assert mode.color_options == ["red", "green", "blue"]
        assert mode.odds == {"red": 2.0, "green": 3.0, "blue": 5.0}
        assert mode.min_bet == Decimal("1.00")
        assert mode.max_bet == Decimal("500.00")
        assert mode.round_duration_seconds == 30
        assert mode.is_active is True


class TestTimedChallengeMode:
    """Tests for Timed Challenge game mode."""

    @pytest.mark.asyncio
    async def test_timed_challenge_mode_creation(self, session: AsyncSession):
        mode = await create_game_mode(
            session,
            name="Speed Round",
            mode_type="timed_challenge",
            color_options=["red", "blue"],
            odds={"red": 1.8, "blue": 1.8},
            min_bet=Decimal("5.00"),
            max_bet=Decimal("200.00"),
            round_duration_seconds=15,
        )
        assert mode.mode_type == "timed_challenge"
        assert mode.round_duration_seconds == 15
        assert mode.round_duration_seconds < 30  # shorter than classic


class TestTournamentMode:
    """Tests for Tournament game mode."""

    @pytest.mark.asyncio
    async def test_tournament_mode_creation(self, session: AsyncSession):
        mode = await create_game_mode(
            session,
            name="Weekly Tournament",
            mode_type="tournament",
            color_options=["red", "green", "blue", "yellow"],
            odds={"red": 2.0, "green": 3.0, "blue": 5.0, "yellow": 10.0},
            min_bet=Decimal("10.00"),
            max_bet=Decimal("1000.00"),
            round_duration_seconds=60,
        )
        assert mode.mode_type == "tournament"
        assert len(mode.color_options) == 4
        assert "yellow" in mode.color_options


class TestModeIndependentConfiguration:
    """Test that each mode has independent configuration."""

    @pytest.mark.asyncio
    async def test_modes_have_independent_config(self, session: AsyncSession):
        classic = await create_game_mode(
            session,
            name="Ind Classic",
            mode_type="classic",
            color_options=["red", "green", "blue"],
            odds={"red": 2.0, "green": 3.0, "blue": 5.0},
            min_bet=Decimal("1.00"),
            max_bet=Decimal("500.00"),
            round_duration_seconds=30,
        )
        timed = await create_game_mode(
            session,
            name="Ind Timed",
            mode_type="timed_challenge",
            color_options=["red", "blue"],
            odds={"red": 1.8, "blue": 1.8},
            min_bet=Decimal("5.00"),
            max_bet=Decimal("200.00"),
            round_duration_seconds=15,
        )
        tournament = await create_game_mode(
            session,
            name="Ind Tournament",
            mode_type="tournament",
            color_options=["red", "green", "blue", "yellow"],
            odds={"red": 2.0, "green": 3.0, "blue": 5.0, "yellow": 10.0},
            min_bet=Decimal("10.00"),
            max_bet=Decimal("1000.00"),
            round_duration_seconds=60,
        )

        # Each mode has its own color_options
        assert classic.color_options != timed.color_options
        assert classic.color_options != tournament.color_options

        # Each mode has its own odds
        assert classic.odds != timed.odds

        # Each mode has its own bet limits
        assert classic.min_bet != timed.min_bet
        assert classic.max_bet != tournament.max_bet

        # Each mode has its own round duration
        assert classic.round_duration_seconds != timed.round_duration_seconds
        assert timed.round_duration_seconds != tournament.round_duration_seconds
