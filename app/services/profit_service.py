"""Profit management service for controlling house profit margins.

This service manages the house profit percentage and winner pool distribution.
When total payouts exceed the available winner pool, payouts are reduced
proportionally so winners share the allocated pool.

Example:
  - 20% house profit, 80% winner pool
  - Total bets: 100,000
  - House keeps: 20,000
  - Winner pool: 80,000
  - If calculated payouts = 90,000, they're reduced to fit 80,000
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import ProfitSettings


@dataclass
class ProfitAllocation:
    """Result of profit allocation calculation for a round."""
    house_profit_percentage: Decimal
    winners_pool_percentage: Decimal
    total_bets: Decimal
    house_profit_amount: Decimal
    winners_pool_amount: Decimal


@dataclass
class PayoutAdjustment:
    """Result of payout adjustment when payouts exceed winner pool."""
    total_calculated_payouts: Decimal
    winners_pool_amount: Decimal
    total_adjusted_payouts: Decimal
    payout_reduced: bool
    reduction_ratio: Decimal  # multiplier to apply to each winner's payout


async def get_active_profit_settings(session: AsyncSession) -> Optional[ProfitSettings]:
    """Get the currently active profit settings.

    Returns None if no active settings exist.
    """
    result = await session.execute(
        select(ProfitSettings)
        .where(ProfitSettings.is_active == True)
        .order_by(ProfitSettings.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def calculate_profit_allocation(
    session: AsyncSession,
    total_bets: Decimal,
) -> ProfitAllocation:
    """Calculate house profit and winner pool based on active settings.

    Args:
        session: Database session
        total_bets: Total amount wagered in the round

    Returns:
        ProfitAllocation with house profit and winner pool amounts
    """
    settings = await get_active_profit_settings(session)

    if not settings:
        # Default: 20% house, 80% winners (if no settings configured)
        house_percentage = Decimal("20.00")
        winners_percentage = Decimal("80.00")
    else:
        house_percentage = settings.house_profit_percentage
        winners_percentage = settings.winners_pool_percentage

    house_profit = (total_bets * house_percentage / Decimal("100")).quantize(Decimal("0.01"))
    winners_pool = (total_bets * winners_percentage / Decimal("100")).quantize(Decimal("0.01"))

    return ProfitAllocation(
        house_profit_percentage=house_percentage,
        winners_pool_percentage=winners_percentage,
        total_bets=total_bets,
        house_profit_amount=house_profit,
        winners_pool_amount=winners_pool,
    )


def adjust_payouts_to_pool(
    total_calculated_payouts: Decimal,
    winners_pool_amount: Decimal,
) -> PayoutAdjustment:
    """Adjust payouts to fit within the winner pool if they exceed it.

    If total calculated payouts > winner pool:
      - Payouts are reduced proportionally
      - reduction_ratio = winners_pool / total_calculated_payouts
      - Each winner gets: original_payout * reduction_ratio

    If total calculated payouts <= winner pool:
      - No adjustment needed
      - Winners get full calculated payouts

    Args:
        total_calculated_payouts: Sum of all calculated winner payouts
        winners_pool_amount: Available pool for winners (total_bets * winners_percentage)

    Returns:
        PayoutAdjustment with reduction ratio and adjusted total
    """
    if total_calculated_payouts > winners_pool_amount:
        # Payouts exceed pool - reduce proportionally
        reduction_ratio = (winners_pool_amount / total_calculated_payouts).quantize(Decimal("0.0001"))
        total_adjusted = winners_pool_amount
        payout_reduced = True
    else:
        # Payouts fit within pool - no reduction
        reduction_ratio = Decimal("1.0000")
        total_adjusted = total_calculated_payouts
        payout_reduced = False

    return PayoutAdjustment(
        total_calculated_payouts=total_calculated_payouts,
        winners_pool_amount=winners_pool_amount,
        total_adjusted_payouts=total_adjusted,
        payout_reduced=payout_reduced,
        reduction_ratio=reduction_ratio,
    )


async def create_profit_settings(
    session: AsyncSession,
    house_profit_percentage: Decimal,
    winners_pool_percentage: Decimal,
) -> ProfitSettings:
    """Create new profit settings and deactivate old ones.

    Args:
        session: Database session
        house_profit_percentage: House profit (0-100)
        winners_pool_percentage: Winner pool (0-100)

    Returns:
        Newly created ProfitSettings

    Raises:
        ValueError: If percentages don't sum to 100
    """
    if house_profit_percentage + winners_pool_percentage != Decimal("100.00"):
        raise ValueError("house_profit_percentage + winners_pool_percentage must equal 100")

    if house_profit_percentage < 0 or winners_pool_percentage < 0:
        raise ValueError("Percentages must be non-negative")

    # Deactivate all existing settings
    result = await session.execute(
        select(ProfitSettings).where(ProfitSettings.is_active == True)
    )
    existing_settings = result.scalars().all()
    for setting in existing_settings:
        setting.is_active = False

    # Create new active settings
    new_settings = ProfitSettings(
        house_profit_percentage=house_profit_percentage,
        winners_pool_percentage=winners_pool_percentage,
        is_active=True,
    )
    session.add(new_settings)
    await session.flush()

    return new_settings


async def update_profit_settings(
    session: AsyncSession,
    house_profit_percentage: Decimal,
    winners_pool_percentage: Decimal,
) -> ProfitSettings:
    """Update profit settings (creates new record and deactivates old).

    Alias for create_profit_settings for clarity.
    """
    return await create_profit_settings(session, house_profit_percentage, winners_pool_percentage)
