"""Integration tests for Stripe deposit/withdrawal flow.

Tests the end-to-end Stripe payment processing with mocked Stripe API,
verifying wallet balance updates, transaction records, and error handling.

Requirements: 2.2, 2.7
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.player import Player, Transaction, TransactionType, Wallet
from app.services import wallet_service


@pytest_asyncio.fixture
async def stripe_player(session: AsyncSession):
    """Create a player with a wallet for Stripe tests."""
    player = Player(
        id=uuid4(),
        email="stripe_test@example.com",
        username="stripeuser",
        password_hash="hashed",
    )
    session.add(player)
    await session.flush()

    wallet = Wallet(
        id=uuid4(),
        player_id=player.id,
        balance=Decimal("100.00"),
        version=0,
    )
    session.add(wallet)
    await session.flush()
    return player, wallet


class TestStripeDeposit:
    """Test Stripe deposit flow with mocked Stripe API."""

    @pytest.mark.asyncio
    async def test_successful_deposit_credits_wallet(self, session, stripe_player):
        """Successful Stripe payment credits the wallet and records transaction."""
        player, wallet = stripe_player

        mock_intent = MagicMock()
        mock_intent.id = "pi_test_123"
        mock_intent.status = "succeeded"

        with patch.object(stripe.PaymentIntent, "create", return_value=mock_intent), \
             patch.object(wallet_service, "_invalidate_balance_cache"), \
             patch("app.services.wallet_service._get_redis", return_value=None), \
             patch("app.services.audit_service.create_audit_entry"):
            txn = await wallet_service.deposit(
                session, player.id, Decimal("50.00"), "pm_test_token"
            )
            await session.commit()

        # Verify transaction record
        assert txn.type == TransactionType.DEPOSIT
        assert txn.amount == Decimal("50.00")
        assert txn.balance_after == Decimal("150.00")
        assert txn.player_id == player.id

        # Verify wallet balance updated
        result = await session.execute(
            select(Wallet).where(Wallet.player_id == player.id)
        )
        updated_wallet = result.scalar_one()
        assert updated_wallet.balance == Decimal("150.00")
        assert updated_wallet.version == 1

    @pytest.mark.asyncio
    async def test_stripe_failure_does_not_credit_wallet(self, session, stripe_player):
        """Stripe API failure should not credit the wallet."""
        player, wallet = stripe_player

        with patch.object(
            stripe.PaymentIntent, "create",
            side_effect=stripe.error.CardError("Card declined", "card", "card_declined"),
        ):
            with pytest.raises(stripe.error.CardError):
                await wallet_service.deposit(
                    session, player.id, Decimal("50.00"), "pm_bad_token"
                )

        # The Stripe error is raised before any wallet mutation occurs,
        # so the in-memory wallet object should still have the original balance.
        assert wallet.balance == Decimal("100.00")

    @pytest.mark.asyncio
    async def test_deposit_records_transaction_with_all_fields(self, session, stripe_player):
        """Deposit transaction has all required fields per Requirement 2.5."""
        player, wallet = stripe_player

        mock_intent = MagicMock()
        mock_intent.id = "pi_test_456"

        with patch.object(stripe.PaymentIntent, "create", return_value=mock_intent), \
             patch.object(wallet_service, "_invalidate_balance_cache"), \
             patch("app.services.wallet_service._get_redis", return_value=None), \
             patch("app.services.audit_service.create_audit_entry"):
            txn = await wallet_service.deposit(
                session, player.id, Decimal("25.00"), "pm_test"
            )
            await session.commit()

        assert txn.id is not None
        assert txn.wallet_id == wallet.id
        assert txn.player_id == player.id
        assert txn.type == TransactionType.DEPOSIT
        assert txn.amount == Decimal("25.00")
        assert txn.balance_after == Decimal("125.00")
        assert txn.created_at is not None


class TestStripeWithdrawal:
    """Test Stripe withdrawal flow with mocked Stripe API."""

    @pytest.mark.asyncio
    async def test_successful_withdrawal_debits_wallet(self, session, stripe_player):
        """Withdrawal deducts from wallet and records transaction."""
        player, wallet = stripe_player

        with patch.object(wallet_service, "_invalidate_balance_cache"), \
             patch("app.services.wallet_service._get_redis", return_value=None), \
             patch("app.services.audit_service.create_audit_entry"):
            txn = await wallet_service.withdraw(
                session, player.id, Decimal("30.00")
            )
            await session.commit()

        assert txn.type == TransactionType.WITHDRAWAL
        assert txn.amount == Decimal("30.00")
        assert txn.balance_after == Decimal("70.00")

        result = await session.execute(
            select(Wallet).where(Wallet.player_id == player.id)
        )
        w = result.scalar_one()
        assert w.balance == Decimal("70.00")

    @pytest.mark.asyncio
    async def test_withdrawal_exceeding_balance_rejected(self, session, stripe_player):
        """Withdrawal exceeding balance raises InsufficientBalanceError."""
        player, wallet = stripe_player
        from app.exceptions import InsufficientBalanceError

        with patch("app.services.wallet_service._get_redis", return_value=None):
            with pytest.raises(InsufficientBalanceError) as exc_info:
                await wallet_service.withdraw(
                    session, player.id, Decimal("200.00")
                )

        assert exc_info.value.balance == Decimal("100.00")
        assert exc_info.value.requested == Decimal("200.00")

    @pytest.mark.asyncio
    async def test_multiple_deposits_and_withdrawal_balance_correct(self, session, stripe_player):
        """Multiple deposits followed by withdrawal yields correct balance."""
        player, wallet = stripe_player

        mock_intent = MagicMock()
        with patch.object(stripe.PaymentIntent, "create", return_value=mock_intent), \
             patch.object(wallet_service, "_invalidate_balance_cache"), \
             patch("app.services.wallet_service._get_redis", return_value=None), \
             patch("app.services.audit_service.create_audit_entry"):
            await wallet_service.deposit(session, player.id, Decimal("50.00"), "pm1")
            await wallet_service.deposit(session, player.id, Decimal("25.00"), "pm2")
            await wallet_service.withdraw(session, player.id, Decimal("75.00"))
            await session.commit()

        result = await session.execute(
            select(Wallet).where(Wallet.player_id == player.id)
        )
        w = result.scalar_one()
        # 100 + 50 + 25 - 75 = 100
        assert w.balance == Decimal("100.00")
