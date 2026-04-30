"""Unit tests for responsible gambling service.

Tests deposit limit CRUD and enforcement, session limit and reminder notification,
self-exclusion for all durations (24h, 7d, 30d, permanent), and loss threshold checks.
Requirements: 10.1, 10.2, 10.3, 10.4, 10.6
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.exceptions import DepositLimitExceededError, SelfExcludedError
from app.models.base import Base
from app.models.player import Player, Transaction, TransactionType, Wallet
from app.models.responsible_gambling import (
    DepositLimit,
    LimitPeriod,
    SelfExclusion,
    SessionLimit,
)
from app.services import responsible_gambling_service as rg_service


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
async def player(session: AsyncSession) -> Player:
    """Create a test player."""
    p = Player(
        id=uuid4(),
        email="rg_test@example.com",
        username="rguser",
        password_hash="hashed",
    )
    session.add(p)
    await session.flush()
    return p


@pytest_asyncio.fixture
async def player_with_wallet(session: AsyncSession, player: Player) -> Player:
    """Create a test player with a wallet."""
    wallet = Wallet(
        id=uuid4(),
        player_id=player.id,
        balance=Decimal("1000.00"),
        version=0,
    )
    session.add(wallet)
    await session.flush()
    return player


# ---------------------------------------------------------------------------
# set_deposit_limit
# ---------------------------------------------------------------------------

class TestSetDepositLimit:
    """Requirement 10.1: Allow player to set daily/weekly/monthly deposit limit."""

    @pytest.mark.asyncio
    async def test_set_daily_limit(self, session, player):
        limit = await rg_service.set_deposit_limit(
            session, player.id, "daily", Decimal("500.00")
        )
        assert limit.period == LimitPeriod.DAILY
        assert limit.amount == Decimal("500.00")
        assert limit.current_usage == Decimal("0.00")
        assert limit.resets_at is not None

    @pytest.mark.asyncio
    async def test_set_weekly_limit(self, session, player):
        limit = await rg_service.set_deposit_limit(
            session, player.id, "weekly", Decimal("2000.00")
        )
        assert limit.period == LimitPeriod.WEEKLY
        assert limit.amount == Decimal("2000.00")

    @pytest.mark.asyncio
    async def test_set_monthly_limit(self, session, player):
        limit = await rg_service.set_deposit_limit(
            session, player.id, "monthly", Decimal("5000.00")
        )
        assert limit.period == LimitPeriod.MONTHLY
        assert limit.amount == Decimal("5000.00")

    @pytest.mark.asyncio
    async def test_update_existing_limit(self, session, player):
        await rg_service.set_deposit_limit(
            session, player.id, "daily", Decimal("500.00")
        )
        updated = await rg_service.set_deposit_limit(
            session, player.id, "daily", Decimal("300.00")
        )
        assert updated.amount == Decimal("300.00")
        assert updated.current_usage == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_multiple_periods_independent(self, session, player):
        daily = await rg_service.set_deposit_limit(
            session, player.id, "daily", Decimal("100.00")
        )
        weekly = await rg_service.set_deposit_limit(
            session, player.id, "weekly", Decimal("500.00")
        )
        assert daily.period != weekly.period
        assert daily.amount == Decimal("100.00")
        assert weekly.amount == Decimal("500.00")


# ---------------------------------------------------------------------------
# check_deposit_limit
# ---------------------------------------------------------------------------

class TestCheckDepositLimit:
    """Requirement 10.2: Reject deposits exceeding limit."""

    @pytest.mark.asyncio
    async def test_no_limits_allows_any_deposit(self, session, player):
        result = await rg_service.check_deposit_limit(
            session, player.id, Decimal("10000.00")
        )
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_deposit_within_limit_allowed(self, session, player):
        await rg_service.set_deposit_limit(
            session, player.id, "daily", Decimal("500.00")
        )
        result = await rg_service.check_deposit_limit(
            session, player.id, Decimal("200.00")
        )
        assert result.allowed is True
        assert result.remaining == Decimal("500.00")

    @pytest.mark.asyncio
    async def test_deposit_exceeding_limit_raises(self, session, player):
        await rg_service.set_deposit_limit(
            session, player.id, "daily", Decimal("500.00")
        )
        with pytest.raises(DepositLimitExceededError) as exc_info:
            await rg_service.check_deposit_limit(
                session, player.id, Decimal("600.00")
            )
        assert exc_info.value.remaining == Decimal("500.00")
        assert exc_info.value.resets_at is not None

    @pytest.mark.asyncio
    async def test_deposit_after_partial_usage_rejected(self, session, player):
        await rg_service.set_deposit_limit(
            session, player.id, "daily", Decimal("500.00")
        )
        # Simulate partial usage
        await rg_service.record_deposit_usage(session, player.id, Decimal("400.00"))

        with pytest.raises(DepositLimitExceededError) as exc_info:
            await rg_service.check_deposit_limit(
                session, player.id, Decimal("200.00")
            )
        assert exc_info.value.remaining == Decimal("100.00")

    @pytest.mark.asyncio
    async def test_deposit_after_partial_usage_within_remaining(self, session, player):
        await rg_service.set_deposit_limit(
            session, player.id, "daily", Decimal("500.00")
        )
        await rg_service.record_deposit_usage(session, player.id, Decimal("300.00"))

        result = await rg_service.check_deposit_limit(
            session, player.id, Decimal("100.00")
        )
        assert result.allowed is True
        assert result.remaining == Decimal("200.00")


# ---------------------------------------------------------------------------
# set_session_limit
# ---------------------------------------------------------------------------

class TestSetSessionLimit:
    """Requirement 10.3: Session time limit with mandatory reminder."""

    @pytest.mark.asyncio
    async def test_set_session_limit(self, session, player):
        await rg_service.set_session_limit(session, player.id, 60)
        limit = await rg_service.get_session_limit(session, player.id)
        assert limit is not None
        assert limit.duration_minutes == 60

    @pytest.mark.asyncio
    async def test_update_session_limit(self, session, player):
        await rg_service.set_session_limit(session, player.id, 60)
        await rg_service.set_session_limit(session, player.id, 120)
        limit = await rg_service.get_session_limit(session, player.id)
        assert limit.duration_minutes == 120

    @pytest.mark.asyncio
    async def test_no_session_limit_returns_none(self, session, player):
        limit = await rg_service.get_session_limit(session, player.id)
        assert limit is None


# ---------------------------------------------------------------------------
# check_loss_threshold
# ---------------------------------------------------------------------------

class TestCheckLossThreshold:
    """Requirement 10.6: Warning when 24h cumulative losses exceed threshold."""

    @pytest.mark.asyncio
    async def test_no_transactions_no_warning(self, session, player_with_wallet):
        result = await rg_service.check_loss_threshold(
            session, player_with_wallet.id, threshold=Decimal("100.00")
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_losses_below_threshold_no_warning(self, session, player_with_wallet):
        # Create bet debit transactions
        wallet_result = await session.execute(
            __import__("sqlalchemy").select(Wallet).where(
                Wallet.player_id == player_with_wallet.id
            )
        )
        wallet = wallet_result.scalar_one()

        txn = Transaction(
            wallet_id=wallet.id,
            player_id=player_with_wallet.id,
            type=TransactionType.BET_DEBIT,
            amount=Decimal("50.00"),
            balance_after=Decimal("950.00"),
        )
        session.add(txn)
        await session.flush()

        result = await rg_service.check_loss_threshold(
            session, player_with_wallet.id, threshold=Decimal("100.00")
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_losses_exceeding_threshold_triggers_warning(self, session, player_with_wallet):
        from sqlalchemy import select as sa_select

        wallet_result = await session.execute(
            sa_select(Wallet).where(Wallet.player_id == player_with_wallet.id)
        )
        wallet = wallet_result.scalar_one()

        # Create bet debits totaling 200
        for _ in range(4):
            txn = Transaction(
                wallet_id=wallet.id,
                player_id=player_with_wallet.id,
                type=TransactionType.BET_DEBIT,
                amount=Decimal("50.00"),
                balance_after=Decimal("800.00"),
            )
            session.add(txn)
        await session.flush()

        result = await rg_service.check_loss_threshold(
            session, player_with_wallet.id, threshold=Decimal("100.00")
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_losses_offset_by_winnings(self, session, player_with_wallet):
        from sqlalchemy import select as sa_select

        wallet_result = await session.execute(
            sa_select(Wallet).where(Wallet.player_id == player_with_wallet.id)
        )
        wallet = wallet_result.scalar_one()

        # Bet debit of 200
        txn1 = Transaction(
            wallet_id=wallet.id,
            player_id=player_with_wallet.id,
            type=TransactionType.BET_DEBIT,
            amount=Decimal("200.00"),
            balance_after=Decimal("800.00"),
        )
        session.add(txn1)

        # Payout credit of 150 (net loss = 50)
        txn2 = Transaction(
            wallet_id=wallet.id,
            player_id=player_with_wallet.id,
            type=TransactionType.PAYOUT_CREDIT,
            amount=Decimal("150.00"),
            balance_after=Decimal("950.00"),
        )
        session.add(txn2)
        await session.flush()

        result = await rg_service.check_loss_threshold(
            session, player_with_wallet.id, threshold=Decimal("100.00")
        )
        # Net loss is 50, threshold is 100 — no warning
        assert result is False


# ---------------------------------------------------------------------------
# self_exclude
# ---------------------------------------------------------------------------

class TestSelfExclude:
    """Requirement 10.4: Self-exclusion for 24h, 7d, 30d, permanent."""

    @pytest.mark.asyncio
    async def test_self_exclude_24h(self, session, player):
        await rg_service.self_exclude(session, player.id, "24h")

        with pytest.raises(SelfExcludedError) as exc_info:
            await rg_service.check_self_exclusion(session, player.id)
        assert exc_info.value.ends_at is not None

    @pytest.mark.asyncio
    async def test_self_exclude_7d(self, session, player):
        await rg_service.self_exclude(session, player.id, "7d")

        with pytest.raises(SelfExcludedError):
            await rg_service.check_self_exclusion(session, player.id)

    @pytest.mark.asyncio
    async def test_self_exclude_30d(self, session, player):
        await rg_service.self_exclude(session, player.id, "30d")

        with pytest.raises(SelfExcludedError):
            await rg_service.check_self_exclusion(session, player.id)

    @pytest.mark.asyncio
    async def test_self_exclude_permanent(self, session, player):
        await rg_service.self_exclude(session, player.id, "permanent")

        with pytest.raises(SelfExcludedError) as exc_info:
            await rg_service.check_self_exclusion(session, player.id)
        assert exc_info.value.ends_at is None

    @pytest.mark.asyncio
    async def test_prevent_reactivation_before_period_ends(self, session, player):
        await rg_service.self_exclude(session, player.id, "24h")

        # Attempting to self-exclude again should raise
        with pytest.raises(SelfExcludedError):
            await rg_service.self_exclude(session, player.id, "7d")

    @pytest.mark.asyncio
    async def test_invalid_duration_raises(self, session, player):
        with pytest.raises(ValueError, match="Invalid exclusion duration"):
            await rg_service.self_exclude(session, player.id, "2h")

    @pytest.mark.asyncio
    async def test_no_exclusion_passes_check(self, session, player):
        # Should not raise
        await rg_service.check_self_exclusion(session, player.id)

    @pytest.mark.asyncio
    async def test_expired_exclusion_auto_deactivates(self, session, player):
        from sqlalchemy import select as sa_select

        # Create an exclusion that already expired
        now = datetime.now(timezone.utc)
        exclusion = SelfExclusion(
            player_id=player.id,
            duration="24h",
            starts_at=now - timedelta(hours=25),
            ends_at=now - timedelta(hours=1),
            is_active=True,
        )
        session.add(exclusion)
        await session.flush()

        # Should not raise — exclusion has expired
        await rg_service.check_self_exclusion(session, player.id)

        # Verify it was deactivated
        result = await session.execute(
            sa_select(SelfExclusion).where(
                SelfExclusion.player_id == player.id
            )
        )
        ex = result.scalar_one()
        assert ex.is_active is False


# ---------------------------------------------------------------------------
# get_deposit_limits
# ---------------------------------------------------------------------------

class TestGetDepositLimits:

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_limits(self, session, player):
        limits = await rg_service.get_deposit_limits(session, player.id)
        assert limits == []

    @pytest.mark.asyncio
    async def test_returns_all_configured_limits(self, session, player):
        await rg_service.set_deposit_limit(session, player.id, "daily", Decimal("100.00"))
        await rg_service.set_deposit_limit(session, player.id, "weekly", Decimal("500.00"))

        limits = await rg_service.get_deposit_limits(session, player.id)
        assert len(limits) == 2
        periods = {l.period for l in limits}
        assert LimitPeriod.DAILY in periods
        assert LimitPeriod.WEEKLY in periods
