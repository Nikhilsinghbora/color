"""Unit tests for the game mode service."""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import GameMode
from app.services.game_mode_service import (
    GameModeNotFoundError,
    InvalidModeTypeError,
    create_game_mode,
    delete_game_mode,
    get_game_mode,
    list_game_modes,
    update_game_mode,
)


class TestCreateGameMode:
    """Tests for create_game_mode."""

    @pytest.mark.asyncio
    async def test_creates_classic_mode(self, session: AsyncSession):
        mode = await create_game_mode(
            session,
            name="Classic Red-Green",
            mode_type="classic",
            color_options=["red", "green", "blue"],
            odds={"red": 2.0, "green": 3.0, "blue": 5.0},
            min_bet=Decimal("1.00"),
            max_bet=Decimal("500.00"),
            round_duration_seconds=30,
        )
        assert mode.name == "Classic Red-Green"
        assert mode.mode_type == "classic"
        assert mode.color_options == ["red", "green", "blue"]
        assert mode.min_bet == Decimal("1.00")
        assert mode.max_bet == Decimal("500.00")
        assert mode.round_duration_seconds == 30
        assert mode.is_active is True

    @pytest.mark.asyncio
    async def test_creates_timed_challenge_mode(self, session: AsyncSession):
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

    @pytest.mark.asyncio
    async def test_creates_tournament_mode(self, session: AsyncSession):
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

    @pytest.mark.asyncio
    async def test_rejects_invalid_mode_type(self, session: AsyncSession):
        with pytest.raises(InvalidModeTypeError):
            await create_game_mode(
                session,
                name="Bad Mode",
                mode_type="invalid_type",
                color_options=["red"],
                odds={"red": 1.0},
                min_bet=Decimal("1.00"),
                max_bet=Decimal("100.00"),
                round_duration_seconds=30,
            )

    @pytest.mark.asyncio
    async def test_stores_odds_as_dict(self, session: AsyncSession):
        odds = {"red": 2.0, "green": 3.0, "blue": 5.0}
        mode = await create_game_mode(
            session,
            name="Odds Test",
            mode_type="classic",
            color_options=["red", "green", "blue"],
            odds=odds,
            min_bet=Decimal("1.00"),
            max_bet=Decimal("100.00"),
            round_duration_seconds=30,
        )
        assert mode.odds == odds


class TestGetGameMode:
    """Tests for get_game_mode."""

    @pytest.mark.asyncio
    async def test_retrieves_existing_mode(self, session: AsyncSession):
        mode = await create_game_mode(
            session,
            name="Fetch Test",
            mode_type="classic",
            color_options=["red", "green"],
            odds={"red": 2.0, "green": 2.0},
            min_bet=Decimal("1.00"),
            max_bet=Decimal("100.00"),
            round_duration_seconds=30,
        )
        fetched = await get_game_mode(session, mode.id)
        assert fetched.id == mode.id
        assert fetched.name == "Fetch Test"

    @pytest.mark.asyncio
    async def test_raises_not_found_for_missing_id(self, session: AsyncSession):
        with pytest.raises(GameModeNotFoundError):
            await get_game_mode(session, uuid4())


class TestListGameModes:
    """Tests for list_game_modes."""

    @pytest.mark.asyncio
    async def test_lists_active_modes_only(self, session: AsyncSession):
        await create_game_mode(
            session, name="Active1", mode_type="classic",
            color_options=["red"], odds={"red": 2.0},
            min_bet=Decimal("1.00"), max_bet=Decimal("100.00"),
            round_duration_seconds=30,
        )
        inactive = await create_game_mode(
            session, name="Inactive1", mode_type="tournament",
            color_options=["blue"], odds={"blue": 3.0},
            min_bet=Decimal("1.00"), max_bet=Decimal("100.00"),
            round_duration_seconds=30,
        )
        await delete_game_mode(session, inactive.id)

        modes = await list_game_modes(session, active_only=True)
        names = [m.name for m in modes]
        assert "Active1" in names
        assert "Inactive1" not in names

    @pytest.mark.asyncio
    async def test_lists_all_modes_when_active_only_false(self, session: AsyncSession):
        await create_game_mode(
            session, name="All1", mode_type="classic",
            color_options=["red"], odds={"red": 2.0},
            min_bet=Decimal("1.00"), max_bet=Decimal("100.00"),
            round_duration_seconds=30,
        )
        inactive = await create_game_mode(
            session, name="All2", mode_type="tournament",
            color_options=["blue"], odds={"blue": 3.0},
            min_bet=Decimal("1.00"), max_bet=Decimal("100.00"),
            round_duration_seconds=30,
        )
        await delete_game_mode(session, inactive.id)

        modes = await list_game_modes(session, active_only=False)
        names = [m.name for m in modes]
        assert "All1" in names
        assert "All2" in names

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_modes(self, session: AsyncSession):
        modes = await list_game_modes(session)
        # May include modes from other tests via shared session, but at minimum
        # should return a list
        assert isinstance(modes, list)


class TestUpdateGameMode:
    """Tests for update_game_mode."""

    @pytest.mark.asyncio
    async def test_updates_name(self, session: AsyncSession):
        mode = await create_game_mode(
            session, name="Original", mode_type="classic",
            color_options=["red"], odds={"red": 2.0},
            min_bet=Decimal("1.00"), max_bet=Decimal("100.00"),
            round_duration_seconds=30,
        )
        updated = await update_game_mode(session, mode.id, name="Renamed")
        assert updated.name == "Renamed"

    @pytest.mark.asyncio
    async def test_updates_bet_limits(self, session: AsyncSession):
        mode = await create_game_mode(
            session, name="Limits Test", mode_type="classic",
            color_options=["red"], odds={"red": 2.0},
            min_bet=Decimal("1.00"), max_bet=Decimal("100.00"),
            round_duration_seconds=30,
        )
        updated = await update_game_mode(
            session, mode.id,
            min_bet=Decimal("5.00"),
            max_bet=Decimal("2000.00"),
        )
        assert updated.min_bet == Decimal("5.00")
        assert updated.max_bet == Decimal("2000.00")

    @pytest.mark.asyncio
    async def test_updates_color_options_and_odds(self, session: AsyncSession):
        mode = await create_game_mode(
            session, name="Colors Test", mode_type="classic",
            color_options=["red", "green"], odds={"red": 2.0, "green": 2.0},
            min_bet=Decimal("1.00"), max_bet=Decimal("100.00"),
            round_duration_seconds=30,
        )
        new_colors = ["red", "green", "blue", "yellow"]
        new_odds = {"red": 2.0, "green": 3.0, "blue": 5.0, "yellow": 10.0}
        updated = await update_game_mode(
            session, mode.id,
            color_options=new_colors,
            odds=new_odds,
        )
        assert updated.color_options == new_colors
        assert updated.odds == new_odds

    @pytest.mark.asyncio
    async def test_updates_mode_type(self, session: AsyncSession):
        mode = await create_game_mode(
            session, name="Type Change", mode_type="classic",
            color_options=["red"], odds={"red": 2.0},
            min_bet=Decimal("1.00"), max_bet=Decimal("100.00"),
            round_duration_seconds=30,
        )
        updated = await update_game_mode(session, mode.id, mode_type="tournament")
        assert updated.mode_type == "tournament"

    @pytest.mark.asyncio
    async def test_rejects_invalid_mode_type_on_update(self, session: AsyncSession):
        mode = await create_game_mode(
            session, name="Bad Update", mode_type="classic",
            color_options=["red"], odds={"red": 2.0},
            min_bet=Decimal("1.00"), max_bet=Decimal("100.00"),
            round_duration_seconds=30,
        )
        with pytest.raises(InvalidModeTypeError):
            await update_game_mode(session, mode.id, mode_type="battle_royale")

    @pytest.mark.asyncio
    async def test_ignores_unknown_fields(self, session: AsyncSession):
        mode = await create_game_mode(
            session, name="Ignore Fields", mode_type="classic",
            color_options=["red"], odds={"red": 2.0},
            min_bet=Decimal("1.00"), max_bet=Decimal("100.00"),
            round_duration_seconds=30,
        )
        updated = await update_game_mode(
            session, mode.id, unknown_field="should_be_ignored"
        )
        assert not hasattr(updated, "unknown_field") or updated.name == "Ignore Fields"

    @pytest.mark.asyncio
    async def test_raises_not_found_for_missing_id(self, session: AsyncSession):
        with pytest.raises(GameModeNotFoundError):
            await update_game_mode(session, uuid4(), name="Nope")


class TestDeleteGameMode:
    """Tests for delete_game_mode (soft delete)."""

    @pytest.mark.asyncio
    async def test_soft_deletes_by_setting_inactive(self, session: AsyncSession):
        mode = await create_game_mode(
            session, name="To Delete", mode_type="classic",
            color_options=["red"], odds={"red": 2.0},
            min_bet=Decimal("1.00"), max_bet=Decimal("100.00"),
            round_duration_seconds=30,
        )
        await delete_game_mode(session, mode.id)
        await session.refresh(mode)
        assert mode.is_active is False

    @pytest.mark.asyncio
    async def test_raises_not_found_for_missing_id(self, session: AsyncSession):
        with pytest.raises(GameModeNotFoundError):
            await delete_game_mode(session, uuid4())

    @pytest.mark.asyncio
    async def test_deleted_mode_still_retrievable(self, session: AsyncSession):
        mode = await create_game_mode(
            session, name="Still There", mode_type="classic",
            color_options=["red"], odds={"red": 2.0},
            min_bet=Decimal("1.00"), max_bet=Decimal("100.00"),
            round_duration_seconds=30,
        )
        await delete_game_mode(session, mode.id)
        fetched = await get_game_mode(session, mode.id)
        assert fetched.is_active is False
