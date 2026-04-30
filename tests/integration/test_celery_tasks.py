"""Integration tests for Celery task dispatch and execution.

Tests withdrawal processing, email delivery, and report generation tasks
running in eager mode (task_always_eager=True).

Requirements: 2.8, 13.6
"""

import logging
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models.base import Base
from app.models.player import Player, Transaction, TransactionType, Wallet


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def task_engine():
    """Dedicated engine for Celery task tests (tasks create their own sessions)."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def task_session_factory(task_engine):
    """Session factory bound to the task engine."""
    return async_sessionmaker(task_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def withdrawal_txn(task_session_factory):
    """Create a player, wallet, and pending withdrawal transaction."""
    async with task_session_factory() as session:
        player = Player(
            id=uuid4(),
            email="celery_test@example.com",
            username="celeryuser",
            password_hash="hashed",
        )
        session.add(player)
        await session.flush()

        wallet = Wallet(
            id=uuid4(),
            player_id=player.id,
            balance=Decimal("50.00"),
            version=0,
        )
        session.add(wallet)
        await session.flush()

        txn = Transaction(
            id=uuid4(),
            wallet_id=wallet.id,
            player_id=player.id,
            type=TransactionType.WITHDRAWAL,
            amount=Decimal("30.00"),
            balance_after=Decimal("20.00"),
            description="Withdrawal of 30.00",
        )
        session.add(txn)
        await session.commit()
        return txn, player, task_session_factory


# ===========================================================================
# Withdrawal Task Tests
# ===========================================================================


class TestWithdrawalTask:
    """Test Celery process_withdrawal task in eager mode."""

    def test_process_withdrawal_success(self, withdrawal_txn, celery_eager_mode):
        """Successful Stripe payout updates transaction description."""
        txn, player, factory = withdrawal_txn

        mock_payout = MagicMock()
        mock_payout.id = "po_test_123"

        with patch("app.tasks.wallet_tasks.async_session_factory", factory), \
             patch.object(stripe.Payout, "create", return_value=mock_payout):
            from app.tasks.wallet_tasks import process_withdrawal
            process_withdrawal.apply(args=[str(txn.id)])

        # Verify transaction was updated
        import asyncio

        async def _check():
            async with factory() as session:
                result = await session.execute(
                    select(Transaction).where(Transaction.id == txn.id)
                )
                t = result.scalar_one()
                assert "processed successfully" in t.description

        asyncio.run(_check())

    def test_process_withdrawal_stripe_failure_retries(self, withdrawal_txn, celery_eager_mode):
        """Stripe failure triggers retry exception in eager mode."""
        txn, player, factory = withdrawal_txn
        from celery.exceptions import Retry as CeleryRetry

        with patch("app.tasks.wallet_tasks.async_session_factory", factory), \
             patch.object(
                 stripe.Payout, "create",
                 side_effect=stripe.error.StripeError("Service unavailable"),
             ):
            from app.tasks.wallet_tasks import process_withdrawal
            # In eager mode with task_eager_propagates=True, the Retry
            # exception propagates. This confirms the retry mechanism works.
            with pytest.raises((CeleryRetry, stripe.error.StripeError)):
                process_withdrawal.apply(args=[str(txn.id)])

    def test_process_withdrawal_missing_transaction(self, withdrawal_txn, celery_eager_mode):
        """Task handles missing transaction gracefully (logs error, no crash)."""
        _, _, factory = withdrawal_txn
        fake_id = str(uuid4())

        with patch("app.tasks.wallet_tasks.async_session_factory", factory), \
             patch.object(stripe.Payout, "create") as mock_create:
            from app.tasks.wallet_tasks import process_withdrawal
            # Should not raise
            process_withdrawal.apply(args=[fake_id])
            mock_create.assert_not_called()


# ===========================================================================
# Email Task Tests
# ===========================================================================


class TestEmailTasks:
    """Test Celery email tasks in eager mode."""

    def test_send_verification_email_dispatches(self, celery_eager_mode):
        """Verification email task executes without error."""
        from app.tasks.email_tasks import send_verification_email

        # With no email_api_key configured, it logs instead of sending
        result = send_verification_email.apply(
            args=[str(uuid4()), "test@example.com"]
        )
        # Task should complete without error
        assert result.successful()

    def test_send_password_reset_email_dispatches(self, celery_eager_mode):
        """Password reset email task executes without error."""
        from app.tasks.email_tasks import send_password_reset_email

        result = send_password_reset_email.apply(
            args=[str(uuid4()), "test@example.com", "reset_token_abc"]
        )
        assert result.successful()

    def test_send_notification_email_dispatches(self, celery_eager_mode):
        """Notification email task executes without error."""
        from app.tasks.email_tasks import send_notification_email

        result = send_notification_email.apply(
            args=[str(uuid4()), "account_locked"],
            kwargs={"email": "test@example.com"},
        )
        assert result.successful()

    def test_email_task_logs_when_no_provider(self, celery_eager_mode, caplog):
        """Email tasks log the email when no provider is configured."""
        from app.tasks.email_tasks import send_verification_email

        with caplog.at_level(logging.INFO):
            send_verification_email.apply(
                args=[str(uuid4()), "log_test@example.com"]
            )

        assert any("log_test@example.com" in r.message for r in caplog.records)


# ===========================================================================
# Report Task Tests
# ===========================================================================


class TestReportTasks:
    """Test Celery report generation tasks in eager mode."""

    def test_generate_daily_report_returns_dict(self, task_session_factory, celery_eager_mode):
        """Daily report task returns a dict with expected keys."""
        with patch("app.tasks.report_tasks.async_session_factory", task_session_factory):
            from app.tasks.report_tasks import generate_daily_report
            result = generate_daily_report.apply()

        report = result.result
        assert isinstance(report, dict)
        assert "report_date" in report
        assert "total_wagering_volume" in report
        assert "total_payouts" in report
        assert "payout_ratio" in report
        assert "flagged_rounds" in report
        assert "responsible_gambling_events" in report

    def test_generate_daily_report_empty_data(self, task_session_factory, celery_eager_mode):
        """Report with no data returns zero values."""
        with patch("app.tasks.report_tasks.async_session_factory", task_session_factory):
            from app.tasks.report_tasks import generate_daily_report
            result = generate_daily_report.apply()

        report = result.result
        assert report["total_wagering_volume"] == "0.00" or report["total_wagering_volume"] == "0"
        assert report["flagged_rounds"] == 0
        assert report["responsible_gambling_events"] == 0
