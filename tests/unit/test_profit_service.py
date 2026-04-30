"""Unit tests for profit_service.

Tests:
- get_active_profit_settings: retrieves active settings
- calculate_profit_allocation: splits total bets into house profit and winner pool
- adjust_payouts_to_pool: reduces payouts when they exceed pool
- create_profit_settings: creates new settings and deactivates old ones
"""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import ProfitSettings
from app.services import profit_service


class TestProfitService:
    """Test profit management service."""

    async def test_get_active_profit_settings_none(self, session: AsyncSession):
        """When no settings exist, returns None."""
        result = await profit_service.get_active_profit_settings(session)
        assert result is None

    async def test_get_active_profit_settings(self, session: AsyncSession):
        """Returns the most recent active setting."""
        setting1 = ProfitSettings(
            house_profit_percentage=Decimal("30.00"),
            winners_pool_percentage=Decimal("70.00"),
            is_active=False,
        )
        setting2 = ProfitSettings(
            house_profit_percentage=Decimal("20.00"),
            winners_pool_percentage=Decimal("80.00"),
            is_active=True,
        )
        session.add_all([setting1, setting2])
        await session.commit()

        result = await profit_service.get_active_profit_settings(session)
        assert result is not None
        assert result.house_profit_percentage == Decimal("20.00")
        assert result.is_active is True

    async def test_calculate_profit_allocation_default(self, session: AsyncSession):
        """Uses default 20/80 split when no settings exist."""
        total_bets = Decimal("10000.00")

        allocation = await profit_service.calculate_profit_allocation(session, total_bets)

        assert allocation.house_profit_percentage == Decimal("20.00")
        assert allocation.winners_pool_percentage == Decimal("80.00")
        assert allocation.total_bets == total_bets
        assert allocation.house_profit_amount == Decimal("2000.00")
        assert allocation.winners_pool_amount == Decimal("8000.00")

    async def test_calculate_profit_allocation_custom(self, session: AsyncSession):
        """Uses custom settings when available."""
        setting = ProfitSettings(
            house_profit_percentage=Decimal("15.00"),
            winners_pool_percentage=Decimal("85.00"),
            is_active=True,
        )
        session.add(setting)
        await session.commit()

        total_bets = Decimal("10000.00")
        allocation = await profit_service.calculate_profit_allocation(session, total_bets)

        assert allocation.house_profit_percentage == Decimal("15.00")
        assert allocation.winners_pool_percentage == Decimal("85.00")
        assert allocation.house_profit_amount == Decimal("1500.00")
        assert allocation.winners_pool_amount == Decimal("8500.00")

    def test_adjust_payouts_no_reduction(self):
        """When payouts fit within pool, no adjustment needed."""
        total_calculated = Decimal("5000.00")
        winners_pool = Decimal("8000.00")

        adjustment = profit_service.adjust_payouts_to_pool(total_calculated, winners_pool)

        assert adjustment.payout_reduced is False
        assert adjustment.reduction_ratio == Decimal("1.0000")
        assert adjustment.total_adjusted_payouts == total_calculated

    def test_adjust_payouts_with_reduction(self):
        """When payouts exceed pool, reduce proportionally."""
        total_calculated = Decimal("10000.00")
        winners_pool = Decimal("8000.00")

        adjustment = profit_service.adjust_payouts_to_pool(total_calculated, winners_pool)

        assert adjustment.payout_reduced is True
        assert adjustment.reduction_ratio == Decimal("0.8000")
        assert adjustment.total_adjusted_payouts == winners_pool

    def test_adjust_payouts_exact_match(self):
        """When payouts exactly match pool, no reduction."""
        total_calculated = Decimal("8000.00")
        winners_pool = Decimal("8000.00")

        adjustment = profit_service.adjust_payouts_to_pool(total_calculated, winners_pool)

        assert adjustment.payout_reduced is False
        assert adjustment.reduction_ratio == Decimal("1.0000")

    async def test_create_profit_settings(self, session: AsyncSession):
        """Creates new settings and marks them active."""
        settings = await profit_service.create_profit_settings(
            session,
            house_profit_percentage=Decimal("25.00"),
            winners_pool_percentage=Decimal("75.00"),
        )
        await session.commit()

        assert settings.house_profit_percentage == Decimal("25.00")
        assert settings.winners_pool_percentage == Decimal("75.00")
        assert settings.is_active is True

    async def test_create_profit_settings_deactivates_old(self, session: AsyncSession):
        """Creating new settings deactivates old ones."""
        old_settings = ProfitSettings(
            house_profit_percentage=Decimal("30.00"),
            winners_pool_percentage=Decimal("70.00"),
            is_active=True,
        )
        session.add(old_settings)
        await session.commit()

        new_settings = await profit_service.create_profit_settings(
            session,
            house_profit_percentage=Decimal("20.00"),
            winners_pool_percentage=Decimal("80.00"),
        )
        await session.commit()
        await session.refresh(old_settings)

        assert old_settings.is_active is False
        assert new_settings.is_active is True

    async def test_create_profit_settings_validation_sum(self, session: AsyncSession):
        """Percentages must sum to 100."""
        with pytest.raises(ValueError, match="must equal 100"):
            await profit_service.create_profit_settings(
                session,
                house_profit_percentage=Decimal("20.00"),
                winners_pool_percentage=Decimal("70.00"),
            )

    async def test_create_profit_settings_validation_negative(self, session: AsyncSession):
        """Percentages must be non-negative."""
        with pytest.raises(ValueError, match="non-negative"):
            await profit_service.create_profit_settings(
                session,
                house_profit_percentage=Decimal("-10.00"),
                winners_pool_percentage=Decimal("110.00"),
            )
