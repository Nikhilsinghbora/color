"""Manually start game rounds for all active game modes.

This is useful for development/testing when Celery Beat is not running.
In production, Celery Beat automatically creates and manages rounds.

Usage:
    python -m scripts.start_rounds
"""

import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from app.models.base import async_session_factory
from app.models.game import GameMode, GameRound, RoundPhase


async def start_rounds():
    """Create initial betting rounds for all active game modes."""
    async with async_session_factory() as session:
        # Get all active game modes
        result = await session.execute(
            select(GameMode).where(GameMode.is_active == True)
        )
        modes = result.scalars().all()

        if not modes:
            print("[ERROR] No active game modes found. Run: python -m scripts.seed_data")
            return

        print(f"Found {len(modes)} active game mode(s)")
        created_count = 0

        for mode in modes:
            # Check if there's already an active round for this mode
            existing_result = await session.execute(
                select(GameRound)
                .where(GameRound.game_mode_id == mode.id)
                .where(GameRound.phase == RoundPhase.BETTING)
            )
            existing = existing_result.scalar_one_or_none()

            if existing:
                print(f"[SKIP] {mode.name} already has an active round: {existing.period_number}")
                continue

            # Create a new round
            now = datetime.now(timezone.utc)
            betting_ends_at = now + timedelta(seconds=mode.round_duration_seconds)

            # Remove timezone info for PostgreSQL TIMESTAMP WITHOUT TIME ZONE
            betting_ends_at = betting_ends_at.replace(tzinfo=None)

            # Generate period number: YYYYMMDD{prefix}{sequence}
            date_str = now.strftime("%Y%m%d")
            period_number = f"{date_str}{mode.mode_prefix}0000001"

            round = GameRound(
                id=uuid4(),
                game_mode_id=mode.id,
                phase=RoundPhase.BETTING,
                betting_ends_at=betting_ends_at,
                period_number=period_number,
                total_bets=Decimal("0.00"),
                total_payouts=Decimal("0.00"),
            )
            session.add(round)
            created_count += 1

            print(f"[OK] Created round for {mode.name}")
            print(f"     Period: {period_number}")
            print(f"     Duration: {mode.round_duration_seconds}s")
            print(f"     Ends at: {betting_ends_at.strftime('%H:%M:%S')}")

        if created_count > 0:
            await session.commit()
            print(f"\n[SUCCESS] Created {created_count} round(s)")
            print("\nNow you can:")
            print("1. Refresh the game page")
            print("2. Place bets before the timer expires")
            print("\nNOTE: For automatic round management, start Celery Beat:")
            print("  celery -A app.celery_app beat --loglevel=info")
        else:
            print("\n[INFO] No new rounds created (all modes have active rounds)")


if __name__ == "__main__":
    print("Starting game rounds...")
    asyncio.run(start_rounds())
