"""Shared test fixtures for the Color Prediction Game tests."""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models.base import Base
from app.models.game import GameMode, GameRound, RoundPhase
from app.models.player import Player, Wallet


@pytest.fixture(scope="session", autouse=True)
def celery_eager_mode():
    """Run all Celery tasks synchronously during tests.

    Sets task_always_eager so .delay() executes inline without a broker.
    Also sets task_eager_propagates so exceptions bubble up in tests.
    """
    from app.celery_app import celery_app

    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )
    yield
    celery_app.conf.update(
        task_always_eager=False,
        task_eager_propagates=False,
    )


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def engine():
    """Create an in-memory SQLite async engine for testing."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    """Provide an async session for each test."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess


@pytest_asyncio.fixture
async def game_mode(session: AsyncSession) -> GameMode:
    """Create a default Classic game mode for testing."""
    mode = GameMode(
        id=uuid4(),
        name="Classic",
        mode_type="classic",
        color_options=["red", "green", "blue"],
        odds={"red": 2.0, "green": 3.0, "blue": 5.0},
        min_bet=Decimal("1.00"),
        max_bet=Decimal("1000.00"),
        round_duration_seconds=30,
    )
    session.add(mode)
    await session.flush()
    return mode


@pytest_asyncio.fixture
async def player_with_wallet(session: AsyncSession):
    """Create a player with a funded wallet for testing."""
    player = Player(
        id=uuid4(),
        email="test@example.com",
        username="testplayer",
        password_hash="hashed_password",
    )
    session.add(player)
    await session.flush()

    wallet = Wallet(
        id=uuid4(),
        player_id=player.id,
        balance=Decimal("500.00"),
    )
    session.add(wallet)
    await session.flush()
    return player, wallet


@pytest_asyncio.fixture
async def betting_round(session: AsyncSession, game_mode: GameMode) -> GameRound:
    """Create a round in BETTING phase."""
    from app.services.game_engine import start_round
    game_round = await start_round(session, game_mode.id)
    return game_round
