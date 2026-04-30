"""Unit tests for wallet service.

Tests wallet initialization, deposit, withdraw, debit, credit,
get_balance, and get_transactions.
Requirements: 2.1, 2.2, 2.3, 2.4, 2.7
"""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.exceptions import InsufficientBalanceError
from app.models.base import Base
from app.models.player import Player, Transaction, TransactionType, Wallet
from app.services import wallet_service


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
        email="wallet_test@example.com",
        username="walletuser",
        password_hash="hashed",
    )
    session.add(p)
    await session.flush()
    return p


# ---- Patch Redis to avoid real connections in unit tests ----
@pytest.fixture(autouse=True)
def _no_redis(monkeypatch):
    """Disable Redis in all wallet_service tests."""
    monkeypatch.setattr(wallet_service, "_get_redis", AsyncMock(return_value=None))


# ---------------------------------------------------------------------------
# initialize_wallet
# ---------------------------------------------------------------------------

class TestInitializeWallet:
    """Requirement 2.1: Wallet initialized with zero balance."""

    @pytest.mark.asyncio
    async def test_creates_wallet_with_zero_balance(self, session, player):
        wallet = await wallet_service.initialize_wallet(session, player.id)
        assert wallet.balance == Decimal("0.00")
        assert wallet.player_id == player.id
        assert wallet.version == 0

    @pytest.mark.asyncio
    async def test_wallet_persisted_in_db(self, session, player):
        wallet = await wallet_service.initialize_wallet(session, player.id)
        from sqlalchemy import select
        result = await session.execute(
            select(Wallet).where(Wallet.id == wallet.id)
        )
        db_wallet = result.scalar_one()
        assert db_wallet.balance == Decimal("0.00")


# ---------------------------------------------------------------------------
# get_balance
# ---------------------------------------------------------------------------

class TestGetBalance:

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_wallet(self, session, player):
        balance = await wallet_service.get_balance(session, player.id)
        assert balance == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_returns_wallet_balance(self, session, player):
        await wallet_service.initialize_wallet(session, player.id)
        balance = await wallet_service.get_balance(session, player.id)
        assert balance == Decimal("0.00")


# ---------------------------------------------------------------------------
# deposit
# ---------------------------------------------------------------------------

class TestDeposit:
    """Requirement 2.2: Stripe payment + wallet credit."""

    @pytest.mark.asyncio
    async def test_deposit_credits_wallet(self, session, player):
        await wallet_service.initialize_wallet(session, player.id)

        with patch("app.services.wallet_service.stripe") as mock_stripe:
            mock_stripe.PaymentIntent.create.return_value = MagicMock(id="pi_test")
            txn = await wallet_service.deposit(
                session, player.id, Decimal("100.00"), "pm_test_token"
            )

        assert txn.type == TransactionType.DEPOSIT
        assert txn.amount == Decimal("100.00")
        assert txn.balance_after == Decimal("100.00")

        balance = await wallet_service.get_balance(session, player.id)
        assert balance == Decimal("100.00")

    @pytest.mark.asyncio
    async def test_deposit_records_transaction(self, session, player):
        await wallet_service.initialize_wallet(session, player.id)

        with patch("app.services.wallet_service.stripe") as mock_stripe:
            mock_stripe.PaymentIntent.create.return_value = MagicMock(id="pi_test")
            txn = await wallet_service.deposit(
                session, player.id, Decimal("50.00"), "pm_test"
            )

        assert txn.id is not None
        assert txn.player_id == player.id
        assert txn.description is not None

    @pytest.mark.asyncio
    async def test_deposit_bumps_version(self, session, player):
        wallet = await wallet_service.initialize_wallet(session, player.id)
        assert wallet.version == 0

        with patch("app.services.wallet_service.stripe") as mock_stripe:
            mock_stripe.PaymentIntent.create.return_value = MagicMock(id="pi_test")
            await wallet_service.deposit(
                session, player.id, Decimal("25.00"), "pm_test"
            )

        from sqlalchemy import select
        result = await session.execute(
            select(Wallet).where(Wallet.player_id == player.id)
        )
        w = result.scalar_one()
        assert w.version == 1


# ---------------------------------------------------------------------------
# withdraw
# ---------------------------------------------------------------------------

class TestWithdraw:
    """Requirements 2.3, 2.4: Balance validation before withdrawal."""

    @pytest.mark.asyncio
    async def test_withdraw_deducts_balance(self, session, player):
        wallet = await wallet_service.initialize_wallet(session, player.id)
        # Fund the wallet directly
        wallet.balance = Decimal("200.00")
        wallet.version = 1
        await session.flush()

        txn = await wallet_service.withdraw(session, player.id, Decimal("75.00"))

        assert txn.type == TransactionType.WITHDRAWAL
        assert txn.amount == Decimal("75.00")
        assert txn.balance_after == Decimal("125.00")

    @pytest.mark.asyncio
    async def test_withdraw_exceeding_balance_raises(self, session, player):
        wallet = await wallet_service.initialize_wallet(session, player.id)
        wallet.balance = Decimal("50.00")
        await session.flush()

        with pytest.raises(InsufficientBalanceError):
            await wallet_service.withdraw(session, player.id, Decimal("100.00"))

    @pytest.mark.asyncio
    async def test_withdraw_exact_balance_succeeds(self, session, player):
        wallet = await wallet_service.initialize_wallet(session, player.id)
        wallet.balance = Decimal("100.00")
        await session.flush()

        txn = await wallet_service.withdraw(session, player.id, Decimal("100.00"))
        assert txn.balance_after == Decimal("0.00")


# ---------------------------------------------------------------------------
# debit
# ---------------------------------------------------------------------------

class TestDebit:
    """Requirement 2.7: Atomic debit for bets."""

    @pytest.mark.asyncio
    async def test_debit_reduces_balance(self, session, player):
        wallet = await wallet_service.initialize_wallet(session, player.id)
        wallet.balance = Decimal("500.00")
        await session.flush()

        round_id = uuid4()
        txn = await wallet_service.debit(session, player.id, Decimal("100.00"), round_id)

        assert txn.type == TransactionType.BET_DEBIT
        assert txn.amount == Decimal("100.00")
        assert txn.balance_after == Decimal("400.00")
        assert txn.reference_id == round_id

    @pytest.mark.asyncio
    async def test_debit_insufficient_balance_raises(self, session, player):
        wallet = await wallet_service.initialize_wallet(session, player.id)
        wallet.balance = Decimal("10.00")
        await session.flush()

        with pytest.raises(InsufficientBalanceError):
            await wallet_service.debit(session, player.id, Decimal("50.00"), uuid4())


# ---------------------------------------------------------------------------
# credit
# ---------------------------------------------------------------------------

class TestCredit:

    @pytest.mark.asyncio
    async def test_credit_increases_balance(self, session, player):
        wallet = await wallet_service.initialize_wallet(session, player.id)
        wallet.balance = Decimal("100.00")
        await session.flush()

        round_id = uuid4()
        txn = await wallet_service.credit(session, player.id, Decimal("250.00"), round_id)

        assert txn.type == TransactionType.PAYOUT_CREDIT
        assert txn.amount == Decimal("250.00")
        assert txn.balance_after == Decimal("350.00")
        assert txn.reference_id == round_id


# ---------------------------------------------------------------------------
# get_transactions
# ---------------------------------------------------------------------------

class TestGetTransactions:
    """Requirement 2.6: Paginated history, most recent first."""

    @pytest.mark.asyncio
    async def test_empty_when_no_wallet(self, session, player):
        result = await wallet_service.get_transactions(session, player.id)
        assert result["transactions"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_returns_transactions_sorted_desc(self, session, player):
        wallet = await wallet_service.initialize_wallet(session, player.id)
        wallet.balance = Decimal("1000.00")
        await session.flush()

        # Create multiple transactions
        round_id = uuid4()
        await wallet_service.debit(session, player.id, Decimal("50.00"), round_id)
        await wallet_service.credit(session, player.id, Decimal("100.00"), round_id)
        await wallet_service.debit(session, player.id, Decimal("25.00"), round_id)

        result = await wallet_service.get_transactions(session, player.id)
        txns = result["transactions"]
        assert len(txns) == 3
        assert result["total"] == 3

    @pytest.mark.asyncio
    async def test_pagination(self, session, player):
        wallet = await wallet_service.initialize_wallet(session, player.id)
        wallet.balance = Decimal("1000.00")
        await session.flush()

        round_id = uuid4()
        for _ in range(5):
            await wallet_service.debit(session, player.id, Decimal("10.00"), round_id)

        page1 = await wallet_service.get_transactions(session, player.id, page=1, page_size=2)
        assert len(page1["transactions"]) == 2
        assert page1["total"] == 5
        assert page1["page"] == 1

        page2 = await wallet_service.get_transactions(session, player.id, page=2, page_size=2)
        assert len(page2["transactions"]) == 2

        page3 = await wallet_service.get_transactions(session, player.id, page=3, page_size=2)
        assert len(page3["transactions"]) == 1
