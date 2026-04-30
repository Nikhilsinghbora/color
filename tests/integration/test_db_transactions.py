"""Integration tests for concurrent wallet operations and deadlock handling.

Tests atomic wallet operations, version-based optimistic locking,
and error handling for concurrent access patterns.

Note: SQLite doesn't support SELECT FOR UPDATE, so these tests validate
the logic and error handling rather than actual row locking.

Requirements: 2.7
"""

from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import InsufficientBalanceError
from app.models.player import Player, Transaction, TransactionType, Wallet
from app.services import wallet_service


@pytest_asyncio.fixture
async def db_player(session: AsyncSession):
    """Create a player with a funded wallet for DB transaction tests."""
    player = Player(
        id=uuid4(),
        email="dbtxn@example.com",
        username="dbtxnuser",
        password_hash="hashed",
    )
    session.add(player)
    await session.flush()

    wallet = Wallet(
        id=uuid4(),
        player_id=player.id,
        balance=Decimal("200.00"),
        version=0,
    )
    session.add(wallet)
    await session.flush()
    return player, wallet


class TestAtomicWalletOperations:
    """Test that wallet operations are atomic and consistent."""

    @pytest.mark.asyncio
    async def test_debit_reduces_balance_exactly(self, session, db_player):
        """Debit reduces balance by exact amount."""
        player, wallet = db_player
        round_id = uuid4()

        with patch("app.services.wallet_service._get_redis", return_value=None), \
             patch.object(wallet_service, "_invalidate_balance_cache"):
            txn = await wallet_service.debit(
                session, player.id, Decimal("75.50"), round_id
            )
            await session.flush()

        assert txn.amount == Decimal("75.50")
        assert txn.balance_after == Decimal("124.50")
        assert txn.type == TransactionType.BET_DEBIT

        result = await session.execute(
            select(Wallet).where(Wallet.player_id == player.id)
        )
        w = result.scalar_one()
        assert w.balance == Decimal("124.50")

    @pytest.mark.asyncio
    async def test_credit_increases_balance_exactly(self, session, db_player):
        """Credit increases balance by exact amount."""
        player, wallet = db_player
        round_id = uuid4()

        with patch("app.services.wallet_service._get_redis", return_value=None), \
             patch.object(wallet_service, "_invalidate_balance_cache"):
            txn = await wallet_service.credit(
                session, player.id, Decimal("50.25"), round_id
            )
            await session.flush()

        assert txn.amount == Decimal("50.25")
        assert txn.balance_after == Decimal("250.25")
        assert txn.type == TransactionType.PAYOUT_CREDIT

    @pytest.mark.asyncio
    async def test_debit_exceeding_balance_rejected(self, session, db_player):
        """Debit exceeding balance raises InsufficientBalanceError."""
        player, wallet = db_player
        round_id = uuid4()

        with patch("app.services.wallet_service._get_redis", return_value=None):
            with pytest.raises(InsufficientBalanceError) as exc_info:
                await wallet_service.debit(
                    session, player.id, Decimal("300.00"), round_id
                )

        assert exc_info.value.balance == Decimal("200.00")
        assert exc_info.value.requested == Decimal("300.00")

    @pytest.mark.asyncio
    async def test_version_increments_on_each_operation(self, session, db_player):
        """Wallet version increments with each operation for optimistic locking."""
        player, wallet = db_player
        round_id = uuid4()

        with patch("app.services.wallet_service._get_redis", return_value=None), \
             patch.object(wallet_service, "_invalidate_balance_cache"):
            await wallet_service.debit(session, player.id, Decimal("10.00"), round_id)
            await session.flush()

            result = await session.execute(
                select(Wallet).where(Wallet.player_id == player.id)
            )
            w = result.scalar_one()
            assert w.version == 1

            await wallet_service.credit(session, player.id, Decimal("5.00"), uuid4())
            await session.flush()

            result = await session.execute(
                select(Wallet).where(Wallet.player_id == player.id)
            )
            w = result.scalar_one()
            assert w.version == 2


class TestSequentialWalletOperations:
    """Test sequential wallet operations maintain consistency."""

    @pytest.mark.asyncio
    async def test_multiple_debits_maintain_balance(self, session, db_player):
        """Multiple sequential debits correctly reduce balance."""
        player, wallet = db_player

        with patch("app.services.wallet_service._get_redis", return_value=None), \
             patch.object(wallet_service, "_invalidate_balance_cache"):
            await wallet_service.debit(session, player.id, Decimal("50.00"), uuid4())
            await wallet_service.debit(session, player.id, Decimal("30.00"), uuid4())
            await wallet_service.debit(session, player.id, Decimal("20.00"), uuid4())
            await session.flush()

        result = await session.execute(
            select(Wallet).where(Wallet.player_id == player.id)
        )
        w = result.scalar_one()
        # 200 - 50 - 30 - 20 = 100
        assert w.balance == Decimal("100.00")

    @pytest.mark.asyncio
    async def test_debit_credit_sequence_balance_correct(self, session, db_player):
        """Interleaved debits and credits yield correct final balance."""
        player, wallet = db_player

        with patch("app.services.wallet_service._get_redis", return_value=None), \
             patch.object(wallet_service, "_invalidate_balance_cache"):
            await wallet_service.debit(session, player.id, Decimal("100.00"), uuid4())
            await wallet_service.credit(session, player.id, Decimal("50.00"), uuid4())
            await wallet_service.debit(session, player.id, Decimal("25.00"), uuid4())
            await wallet_service.credit(session, player.id, Decimal("75.00"), uuid4())
            await session.flush()

        result = await session.execute(
            select(Wallet).where(Wallet.player_id == player.id)
        )
        w = result.scalar_one()
        # 200 - 100 + 50 - 25 + 75 = 200
        assert w.balance == Decimal("200.00")

    @pytest.mark.asyncio
    async def test_failed_debit_does_not_affect_balance(self, session, db_player):
        """A failed debit (insufficient balance) leaves balance unchanged."""
        player, wallet = db_player

        with patch("app.services.wallet_service._get_redis", return_value=None), \
             patch.object(wallet_service, "_invalidate_balance_cache"):
            # Successful debit
            await wallet_service.debit(session, player.id, Decimal("180.00"), uuid4())
            await session.flush()

            # This should fail — only 20.00 left
            with pytest.raises(InsufficientBalanceError):
                await wallet_service.debit(session, player.id, Decimal("50.00"), uuid4())

        result = await session.execute(
            select(Wallet).where(Wallet.player_id == player.id)
        )
        w = result.scalar_one()
        assert w.balance == Decimal("20.00")

    @pytest.mark.asyncio
    async def test_all_transactions_recorded(self, session, db_player):
        """Every operation creates a transaction record."""
        player, wallet = db_player

        with patch("app.services.wallet_service._get_redis", return_value=None), \
             patch.object(wallet_service, "_invalidate_balance_cache"):
            await wallet_service.debit(session, player.id, Decimal("10.00"), uuid4())
            await wallet_service.credit(session, player.id, Decimal("5.00"), uuid4())
            await wallet_service.debit(session, player.id, Decimal("3.00"), uuid4())
            await session.flush()

        result = await session.execute(
            select(Transaction).where(Transaction.player_id == player.id)
        )
        transactions = result.scalars().all()
        assert len(transactions) == 3

        types = [t.type for t in transactions]
        assert types.count(TransactionType.BET_DEBIT) == 2
        assert types.count(TransactionType.PAYOUT_CREDIT) == 1


class TestDeadlockHandling:
    """Test error handling for concurrent-like access patterns.

    SQLite doesn't support FOR UPDATE, so we test the error handling
    logic rather than actual row locking.
    """

    @pytest.mark.asyncio
    async def test_insufficient_balance_error_is_descriptive(self, session, db_player):
        """InsufficientBalanceError contains balance and requested amount."""
        player, wallet = db_player

        with patch("app.services.wallet_service._get_redis", return_value=None):
            with pytest.raises(InsufficientBalanceError) as exc_info:
                await wallet_service.debit(
                    session, player.id, Decimal("999.99"), uuid4()
                )

        err = exc_info.value
        assert err.balance == Decimal("200.00")
        assert err.requested == Decimal("999.99")
        assert "insufficient" in str(err).lower()

    @pytest.mark.asyncio
    async def test_wallet_balance_never_negative(self, session, db_player):
        """Wallet balance cannot go negative through any operation sequence."""
        player, wallet = db_player

        with patch("app.services.wallet_service._get_redis", return_value=None), \
             patch.object(wallet_service, "_invalidate_balance_cache"):
            # Drain the wallet
            await wallet_service.debit(session, player.id, Decimal("200.00"), uuid4())
            await session.flush()

            # Any further debit should fail
            with pytest.raises(InsufficientBalanceError):
                await wallet_service.debit(session, player.id, Decimal("0.01"), uuid4())

        result = await session.execute(
            select(Wallet).where(Wallet.player_id == player.id)
        )
        w = result.scalar_one()
        assert w.balance == Decimal("0.00")
