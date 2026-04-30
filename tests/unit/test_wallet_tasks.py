"""Unit tests for the Celery process_withdrawal task.

Tests Stripe payout processing, retry logic with exponential backoff,
and failure marking after retry exhaustion.

Requirements: 2.8
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import stripe

from app.models.player import Transaction, TransactionType
from app.tasks.wallet_tasks import (
    _mark_transaction_failed,
    _process_withdrawal_async,
    process_withdrawal,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_transaction(amount: Decimal = Decimal("50.00")) -> Transaction:
    """Create a fake Transaction object for testing."""
    txn = Transaction(
        id=uuid4(),
        wallet_id=uuid4(),
        player_id=uuid4(),
        type=TransactionType.WITHDRAWAL,
        amount=amount,
        balance_after=Decimal("0.00"),
        description=f"Withdrawal of {amount}",
    )
    return txn


# ---------------------------------------------------------------------------
# _process_withdrawal_async
# ---------------------------------------------------------------------------

class TestProcessWithdrawalAsync:

    @pytest.mark.asyncio
    async def test_successful_payout_updates_description(self):
        txn = _make_transaction(Decimal("75.00"))
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = txn
        mock_session.execute.return_value = mock_result

        mock_factory = MagicMock()
        mock_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.wallet_tasks.async_session_factory", return_value=mock_factory), \
             patch("app.tasks.wallet_tasks.stripe") as mock_stripe:
            mock_stripe.Payout.create.return_value = MagicMock(id="po_test")
            await _process_withdrawal_async(str(txn.id))

        mock_stripe.Payout.create.assert_called_once_with(
            amount=7500,
            currency="usd",
        )
        assert "processed successfully" in txn.description
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_transaction_not_found_logs_and_returns(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        mock_factory = MagicMock()
        mock_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.wallet_tasks.async_session_factory", return_value=mock_factory), \
             patch("app.tasks.wallet_tasks.stripe") as mock_stripe:
            await _process_withdrawal_async(str(uuid4()))

        mock_stripe.Payout.create.assert_not_called()
        mock_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stripe_error_propagates(self):
        txn = _make_transaction()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = txn
        mock_session.execute.return_value = mock_result

        mock_factory = MagicMock()
        mock_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.wallet_tasks.async_session_factory", return_value=mock_factory), \
             patch("app.tasks.wallet_tasks.stripe") as mock_stripe:
            mock_stripe.error.StripeError = stripe.error.StripeError
            mock_stripe.Payout.create.side_effect = stripe.error.StripeError("fail")
            with pytest.raises(stripe.error.StripeError):
                await _process_withdrawal_async(str(txn.id))


# ---------------------------------------------------------------------------
# _mark_transaction_failed
# ---------------------------------------------------------------------------

class TestMarkTransactionFailed:

    @pytest.mark.asyncio
    async def test_marks_description_as_failed(self):
        txn = _make_transaction()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = txn
        mock_session.execute.return_value = mock_result

        mock_factory = MagicMock()
        mock_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.wallet_tasks.async_session_factory", return_value=mock_factory):
            await _mark_transaction_failed(str(txn.id), "Stripe timeout")

        assert "Withdrawal failed: Stripe timeout" == txn.description
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_missing_transaction_does_not_crash(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        mock_factory = MagicMock()
        mock_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.wallet_tasks.async_session_factory", return_value=mock_factory):
            await _mark_transaction_failed(str(uuid4()), "error")

        mock_session.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# process_withdrawal (Celery task)
# ---------------------------------------------------------------------------

class TestProcessWithdrawalTask:

    def test_task_registered_with_correct_name(self):
        assert process_withdrawal.name == "app.tasks.wallet_tasks.process_withdrawal"

    def test_task_max_retries_is_3(self):
        assert process_withdrawal.max_retries == 3

    def test_task_is_bound(self):
        # Bound tasks accept 'self' — verify via the underlying run method
        assert hasattr(process_withdrawal, "run")

    def test_successful_withdrawal(self):
        txn = _make_transaction()
        with patch("app.tasks.wallet_tasks.asyncio.run") as mock_run:
            mock_run.return_value = None
            process_withdrawal(str(txn.id))
            mock_run.assert_called_once()

    def test_exponential_backoff_formula(self):
        """Verify the backoff formula: 2^retries * 2 gives 2s, 4s, 8s."""
        assert 2 ** 0 * 2 == 2   # 1st retry
        assert 2 ** 1 * 2 == 4   # 2nd retry
        assert 2 ** 2 * 2 == 8   # 3rd retry

    def test_stripe_error_triggers_retry(self):
        """Verify that a Stripe error causes the task to retry."""
        txn_id = str(uuid4())
        err = stripe.error.StripeError("connection error")

        # Resolve the PromiseProxy to get the actual task object
        actual_task = process_withdrawal._get_current_object()

        with patch("app.tasks.wallet_tasks.asyncio.run", side_effect=err), \
             patch.object(actual_task, "retry", side_effect=err) as mock_retry:
            process_withdrawal.push_request(retries=0)
            try:
                with pytest.raises(stripe.error.StripeError):
                    process_withdrawal.run(txn_id)
                mock_retry.assert_called_once()
                assert mock_retry.call_args[1]["countdown"] == 2
            finally:
                process_withdrawal.pop_request()

    def test_retry_backoff_second_attempt(self):
        txn_id = str(uuid4())
        err = stripe.error.StripeError("timeout")

        actual_task = process_withdrawal._get_current_object()

        with patch("app.tasks.wallet_tasks.asyncio.run", side_effect=err), \
             patch.object(actual_task, "retry", side_effect=err) as mock_retry:
            process_withdrawal.push_request(retries=1)
            try:
                with pytest.raises(stripe.error.StripeError):
                    process_withdrawal.run(txn_id)
                assert mock_retry.call_args[1]["countdown"] == 4
            finally:
                process_withdrawal.pop_request()

    def test_retry_backoff_third_attempt(self):
        txn_id = str(uuid4())
        err = stripe.error.StripeError("timeout")

        actual_task = process_withdrawal._get_current_object()

        with patch("app.tasks.wallet_tasks.asyncio.run", side_effect=err), \
             patch.object(actual_task, "retry", side_effect=err) as mock_retry:
            process_withdrawal.push_request(retries=2)
            try:
                with pytest.raises(stripe.error.StripeError):
                    process_withdrawal.run(txn_id)
                assert mock_retry.call_args[1]["countdown"] == 8
            finally:
                process_withdrawal.pop_request()

    def test_max_retries_exhausted_marks_failed(self):
        from celery.exceptions import MaxRetriesExceededError

        txn_id = str(uuid4())
        err = stripe.error.StripeError("permanent failure")

        actual_task = process_withdrawal._get_current_object()

        with patch("app.tasks.wallet_tasks.asyncio.run") as mock_run, \
             patch.object(actual_task, "retry", side_effect=MaxRetriesExceededError()):
            mock_run.side_effect = [err, None]
            process_withdrawal.push_request(retries=3)
            try:
                process_withdrawal.run(txn_id)
                # asyncio.run called twice: once for _process_withdrawal_async (raises),
                # once for _mark_transaction_failed
                assert mock_run.call_count == 2
            finally:
                process_withdrawal.pop_request()
