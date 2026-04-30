"""Seed the database with initial game modes.

Run: python -m scripts.seed_data
"""

import asyncio
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

from app.models.base import async_session_factory, engine, Base
from app.models.game import GameMode


GAME_MODES = [
    {
        "name": "Win Go 30s",
        "mode_type": "classic",
        "color_options": ["green", "red", "violet"],
        "odds": {
            "green": "2.0",
            "red": "2.0",
            "violet": "4.8",
            "number": "9.6",
            "big": "2.0",
            "small": "2.0",
        },
        "min_bet": Decimal("1.00"),
        "max_bet": Decimal("10000.00"),
        "round_duration_seconds": 30,
        "mode_prefix": "100",
        "is_active": True,
    },
    {
        "name": "Win Go 1Min",
        "mode_type": "classic",
        "color_options": ["green", "red", "violet"],
        "odds": {
            "green": "2.0",
            "red": "2.0",
            "violet": "4.8",
            "number": "9.6",
            "big": "2.0",
            "small": "2.0",
        },
        "min_bet": Decimal("1.00"),
        "max_bet": Decimal("10000.00"),
        "round_duration_seconds": 60,
        "mode_prefix": "101",
        "is_active": True,
    },
    {
        "name": "Win Go 3Min",
        "mode_type": "classic",
        "color_options": ["green", "red", "violet"],
        "odds": {
            "green": "2.0",
            "red": "2.0",
            "violet": "4.8",
            "number": "9.6",
            "big": "2.0",
            "small": "2.0",
        },
        "min_bet": Decimal("1.00"),
        "max_bet": Decimal("10000.00"),
        "round_duration_seconds": 180,
        "mode_prefix": "102",
        "is_active": True,
    },
    {
        "name": "Win Go 5Min",
        "mode_type": "classic",
        "color_options": ["green", "red", "violet"],
        "odds": {
            "green": "2.0",
            "red": "2.0",
            "violet": "4.8",
            "number": "9.6",
            "big": "2.0",
            "small": "2.0",
        },
        "min_bet": Decimal("1.00"),
        "max_bet": Decimal("10000.00"),
        "round_duration_seconds": 300,
        "mode_prefix": "103",
        "is_active": True,
    },
]


async def seed():
    async with async_session_factory() as session:
        # Check if modes already exist
        result = await session.execute(select(GameMode).limit(1))
        if result.scalar_one_or_none() is not None:
            print("Game modes already exist — skipping seed.")
            return

        for mode_data in GAME_MODES:
            mode = GameMode(id=uuid4(), **mode_data)
            session.add(mode)

        await session.commit()
        print(f"Seeded {len(GAME_MODES)} game modes.")


if __name__ == "__main__":
    asyncio.run(seed())
