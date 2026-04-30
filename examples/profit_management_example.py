"""Example: Using the Profit Management System

This script demonstrates how admins can configure and use the profit
management system to control house profit margins.
"""

import asyncio
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import async_session_factory
from app.services import profit_service


async def example_create_profit_settings():
    """Example: Create profit settings (20% house, 80% winners)."""
    async with async_session_factory() as session:
        settings = await profit_service.create_profit_settings(
            session,
            house_profit_percentage=Decimal("20.00"),
            winners_pool_percentage=Decimal("80.00"),
        )
        await session.commit()

        print("✓ Created profit settings:")
        print(f"  House profit: {settings.house_profit_percentage}%")
        print(f"  Winner pool: {settings.winners_pool_percentage}%")
        print(f"  Active: {settings.is_active}")


async def example_get_active_settings():
    """Example: Get currently active profit settings."""
    async with async_session_factory() as session:
        settings = await profit_service.get_active_profit_settings(session)

        if settings:
            print("✓ Active profit settings:")
            print(f"  House profit: {settings.house_profit_percentage}%")
            print(f"  Winner pool: {settings.winners_pool_percentage}%")
        else:
            print("ℹ No profit settings configured (using defaults)")


async def example_calculate_profit_allocation():
    """Example: Calculate profit allocation for a round."""
    async with async_session_factory() as session:
        total_bets = Decimal("100000.00")  # $100,000 in bets

        allocation = await profit_service.calculate_profit_allocation(
            session, total_bets
        )

        print(f"\n✓ Profit allocation for ${total_bets}:")
        print(f"  House profit ({allocation.house_profit_percentage}%): ${allocation.house_profit_amount}")
        print(f"  Winner pool ({allocation.winners_pool_percentage}%): ${allocation.winners_pool_amount}")


def example_adjust_payouts_no_reduction():
    """Example: Payouts fit within winner pool (no reduction)."""
    total_calculated_payouts = Decimal("60000.00")  # $60,000 winners
    winners_pool_amount = Decimal("80000.00")       # $80,000 available

    adjustment = profit_service.adjust_payouts_to_pool(
        total_calculated_payouts,
        winners_pool_amount,
    )

    print("\n✓ Scenario 1: Payouts fit within pool")
    print(f"  Calculated payouts: ${total_calculated_payouts}")
    print(f"  Winner pool: ${winners_pool_amount}")
    print(f"  Reduction needed: {adjustment.payout_reduced}")
    print(f"  Reduction ratio: {adjustment.reduction_ratio}")
    print(f"  Actual payouts: ${adjustment.total_adjusted_payouts}")


def example_adjust_payouts_with_reduction():
    """Example: Payouts exceed winner pool (reduction required)."""
    total_calculated_payouts = Decimal("90000.00")  # $90,000 winners
    winners_pool_amount = Decimal("80000.00")       # $80,000 available

    adjustment = profit_service.adjust_payouts_to_pool(
        total_calculated_payouts,
        winners_pool_amount,
    )

    print("\n✓ Scenario 2: Payouts exceed pool (REDUCTION)")
    print(f"  Calculated payouts: ${total_calculated_payouts}")
    print(f"  Winner pool: ${winners_pool_amount}")
    print(f"  Exceeds by: ${total_calculated_payouts - winners_pool_amount}")
    print(f"  Reduction needed: {adjustment.payout_reduced}")
    print(f"  Reduction ratio: {adjustment.reduction_ratio}")
    print(f"  Actual payouts: ${adjustment.total_adjusted_payouts}")

    # Show individual winner impact
    print("\n  Individual winner examples:")
    example_payouts = [
        Decimal("1000.00"),
        Decimal("2500.00"),
        Decimal("5000.00"),
    ]
    for original in example_payouts:
        adjusted = (original * adjustment.reduction_ratio).quantize(Decimal("0.01"))
        reduction_amount = original - adjusted
        print(f"    Original: ${original:>8} → Adjusted: ${adjusted:>8} (reduced ${reduction_amount})")


async def example_update_settings_for_promotion():
    """Example: Temporary promotion with better player odds."""
    async with async_session_factory() as session:
        # Normal settings: 20% house, 80% winners
        print("\n✓ Normal settings:")
        print("  House: 20%, Winners: 80%")

        # Promotion settings: 5% house, 95% winners
        promo_settings = await profit_service.create_profit_settings(
            session,
            house_profit_percentage=Decimal("5.00"),
            winners_pool_percentage=Decimal("95.00"),
        )
        await session.commit()

        print("\n✓ Promotion settings activated:")
        print(f"  House: {promo_settings.house_profit_percentage}% (was 20%)")
        print(f"  Winners: {promo_settings.winners_pool_percentage}% (was 80%)")
        print("  → Players get 95% of bets as winner pool!")

        # Show impact
        total_bets = Decimal("100000.00")
        allocation = await profit_service.calculate_profit_allocation(
            session, total_bets
        )
        print(f"\n  For ${total_bets} in bets:")
        print(f"    House: ${allocation.house_profit_amount} (only 5%!)")
        print(f"    Winners: ${allocation.winners_pool_amount} (95%!)")


async def example_aggressive_margin():
    """Example: Aggressive margin for high-revenue periods."""
    async with async_session_factory() as session:
        # Aggressive settings: 30% house, 70% winners
        settings = await profit_service.create_profit_settings(
            session,
            house_profit_percentage=Decimal("30.00"),
            winners_pool_percentage=Decimal("70.00"),
        )
        await session.commit()

        print("\n✓ Aggressive margin settings:")
        print(f"  House: {settings.house_profit_percentage}%")
        print(f"  Winners: {settings.winners_pool_percentage}%")

        total_bets = Decimal("100000.00")
        allocation = await profit_service.calculate_profit_allocation(
            session, total_bets
        )
        print(f"\n  For ${total_bets} in bets:")
        print(f"    House: ${allocation.house_profit_amount} (30%)")
        print(f"    Winners: ${allocation.winners_pool_amount} (70%)")
        print("  ⚠ Warning: Higher chance of payout reductions!")


async def main():
    """Run all examples."""
    print("=" * 60)
    print("Profit Management System Examples")
    print("=" * 60)

    # Example 1: Create settings
    # await example_create_profit_settings()

    # Example 2: Get active settings
    await example_get_active_settings()

    # Example 3: Calculate allocation
    await example_calculate_profit_allocation()

    # Example 4: No reduction scenario
    example_adjust_payouts_no_reduction()

    # Example 5: Reduction scenario
    example_adjust_payouts_with_reduction()

    # Example 6: Promotion settings
    # await example_update_settings_for_promotion()

    # Example 7: Aggressive margin
    # await example_aggressive_margin()

    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    # Note: Uncomment the examples you want to run in main()
    # Some examples create database records, so be careful!
    asyncio.run(main())
