"""Celery tasks for wallet withdrawal processing.

Processes Stripe payouts asynchronously with retry logic
(3 retries, exponential backoff: 2s, 4s, 8s).

Requirements: 2.8
"""

import asyncio
import logging
from uuid import UUID

import stripe
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select

from app.celery_app import celery_app
from app.config import settings
from app.models.base import celery_session, dispose_celery_engine
from app.models.player import Transaction

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from synchronous Celery worker context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(dispose_celery_engine())
        loop.close()


async def _process_withdrawal_async(transaction_id: str) -> None:
    """Look up the transaction and call Stripe Payout.create.

    Raises stripe.error.StripeError on Stripe failures so the caller
    can decide whether to retry.
    """
    async with celery_session() as session:
        result = await session.execute(
            select(Transaction).where(Transaction.id == UUID(transaction_id))
        )
        transaction = result.scalar_one_or_none()
        if transaction is None:
            logger.error("Transaction %s not found", transaction_id)
            return

        stripe.api_key = settings.stripe_secret_key
        stripe.Payout.create(
            amount=int(transaction.amount * 100),
            currency="usd",
        )

        transaction.description = f"Withdrawal of {transaction.amount} processed successfully"
        await session.commit()


async def _mark_transaction_failed(transaction_id: str, error_msg: str) -> None:
    """Mark the transaction description as failed after retry exhaustion."""
    async with celery_session() as session:
        result = await session.execute(
            select(Transaction).where(Transaction.id == UUID(transaction_id))
        )
        transaction = result.scalar_one_or_none()
        if transaction is not None:
            transaction.description = f"Withdrawal failed: {error_msg}"
            await session.commit()


@celery_app.task(
    name="app.tasks.wallet_tasks.process_withdrawal",
    bind=True,
    max_retries=3,
)
def process_withdrawal(self, transaction_id: str) -> None:
    """Process a Stripe payout for a withdrawal transaction.

    Retries up to 3 times with exponential backoff (2s, 4s, 8s).
    Marks the transaction as failed after all retries are exhausted.
    """
    try:
        _run_async(_process_withdrawal_async(transaction_id))
    except stripe.error.StripeError as exc:
        logger.warning(
            "Stripe error for transaction %s (attempt %d/%d): %s",
            transaction_id,
            self.request.retries + 1,
            self.max_retries,
            str(exc),
        )
        try:
            self.retry(exc=exc, countdown=2 ** self.request.retries * 2)
        except MaxRetriesExceededError:
            logger.error(
                "Max retries exhausted for transaction %s: %s",
                transaction_id,
                str(exc),
            )
            _run_async(_mark_transaction_failed(transaction_id, str(exc)))
