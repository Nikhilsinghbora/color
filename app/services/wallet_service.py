"""Wallet service for managing player balances and transactions.

Provides atomic wallet operations using SELECT ... FOR UPDATE and optimistic
locking via the version column. Uses Redis cache for balance reads with 30s TTL
and DB fallback. Records every transaction with unique ID, timestamp, amount,
type, and resulting balance.

Requirements: 2.1, 2.2, 2.3, 2.5, 2.6, 2.7
"""

import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID

import redis.asyncio as aioredis
import stripe
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import InsufficientBalanceError
from app.models.player import Transaction, TransactionType, Wallet

logger = logging.getLogger(__name__)

# Redis key pattern and TTL for cached wallet balance
_BALANCE_CACHE_KEY = "wallet:{player_id}:balance"
_BALANCE_CACHE_TTL = 30  # seconds


def _balance_key(player_id: UUID) -> str:
    """Return the Redis key for a player's cached balance."""
    return _BALANCE_CACHE_KEY.format(player_id=player_id)


async def _get_redis() -> Optional[aioredis.Redis]:
    """Return a Redis client, or None if connection fails."""
    try:
        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        return client
    except Exception:
        logger.warning("Redis unavailable, falling back to DB for balance")
        return None


async def _invalidate_balance_cache(player_id: UUID) -> None:
    """Delete the cached balance for a player so the next read hits DB."""
    client = await _get_redis()
    if client:
        try:
            await client.delete(_balance_key(player_id))
        except Exception:
            logger.warning("Failed to invalidate balance cache for %s", player_id)
        finally:
            await client.aclose()


async def _set_balance_cache(player_id: UUID, balance: Decimal) -> None:
    """Cache the wallet balance in Redis with TTL."""
    client = await _get_redis()
    if client:
        try:
            await client.set(
                _balance_key(player_id),
                str(balance),
                ex=_BALANCE_CACHE_TTL,
            )
        except Exception:
            logger.warning("Failed to cache balance for %s", player_id)
        finally:
            await client.aclose()


async def _get_balance_from_cache(player_id: UUID) -> Optional[Decimal]:
    """Try to read the cached balance from Redis. Returns None on miss/error."""
    client = await _get_redis()
    if client:
        try:
            val = await client.get(_balance_key(player_id))
            if val is not None:
                return Decimal(val)
        except Exception:
            logger.warning("Failed to read balance cache for %s", player_id)
        finally:
            await client.aclose()
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_balance(session: AsyncSession, player_id: UUID) -> Decimal:
    """Return the current wallet balance for a player.

    Checks Redis cache first (30s TTL). Falls back to DB on cache miss.
    """
    cached = await _get_balance_from_cache(player_id)
    if cached is not None:
        return cached

    result = await session.execute(
        select(Wallet).where(Wallet.player_id == player_id)
    )
    wallet = result.scalar_one_or_none()
    if wallet is None:
        return Decimal("0.00")

    await _set_balance_cache(player_id, wallet.balance)
    return wallet.balance


async def initialize_wallet(session: AsyncSession, player_id: UUID) -> Wallet:
    """Create a wallet with zero balance for a newly registered player.

    Requirement 2.1: Initialize wallet with zero balance on registration.
    """
    wallet = Wallet(
        player_id=player_id,
        balance=Decimal("0.00"),
        version=0,
    )
    session.add(wallet)
    await session.flush()
    return wallet


async def deposit(
    session: AsyncSession,
    player_id: UUID,
    amount: Decimal,
    stripe_token: str,
    ip_address: str | None = None,
) -> Transaction:
    """Process a Stripe payment and credit the wallet atomically.

    1. Charge via Stripe PaymentIntent
    2. Lock wallet row with SELECT ... FOR UPDATE
    3. Credit balance, bump version
    4. Record DEPOSIT transaction
    5. Invalidate Redis balance cache

    Requirement 2.2: Process payment and credit within 5s of confirmation.
    """
    # --- Stripe charge ---
    stripe.api_key = settings.stripe_secret_key
    stripe.PaymentIntent.create(
        amount=int(amount * 100),  # Stripe expects cents
        currency="usd",
        payment_method=stripe_token,
        confirm=True,
        automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
    )

    # --- Atomic wallet update ---
    result = await session.execute(
        select(Wallet).where(Wallet.player_id == player_id).with_for_update()
    )
    wallet = result.scalar_one()

    wallet.balance += amount
    wallet.version += 1

    transaction = Transaction(
        wallet_id=wallet.id,
        player_id=player_id,
        type=TransactionType.DEPOSIT,
        amount=amount,
        balance_after=wallet.balance,
        description=f"Deposit of {amount}",
    )
    session.add(transaction)
    await session.flush()

    await _invalidate_balance_cache(player_id)

    # Audit: wallet deposit
    from app.services.audit_service import create_audit_entry
    from app.models.audit import AuditEventType

    await create_audit_entry(
        session,
        event_type=AuditEventType.WALLET_DEPOSIT,
        actor_id=player_id,
        details={"amount": str(amount), "balance_after": str(wallet.balance)},
        ip_address=ip_address,
    )

    return transaction


async def withdraw(
    session: AsyncSession,
    player_id: UUID,
    amount: Decimal,
    ip_address: str | None = None,
) -> Transaction:
    """Validate balance and create a PENDING withdrawal transaction.

    The actual Stripe payout is handled asynchronously by a Celery task
    (task 6.3). This function only validates and records the intent.

    Requirement 2.3 / 2.4: Verify balance before processing withdrawal.
    Requirement 2.8: Dispatch withdrawal as async Celery task.
    """
    result = await session.execute(
        select(Wallet).where(Wallet.player_id == player_id).with_for_update()
    )
    wallet = result.scalar_one()

    if wallet.balance < amount:
        raise InsufficientBalanceError(balance=wallet.balance, requested=amount)

    wallet.balance -= amount
    wallet.version += 1

    transaction = Transaction(
        wallet_id=wallet.id,
        player_id=player_id,
        type=TransactionType.WITHDRAWAL,
        amount=amount,
        balance_after=wallet.balance,
        description=f"Withdrawal of {amount}",
    )
    session.add(transaction)
    await session.flush()

    await _invalidate_balance_cache(player_id)

    # Audit: wallet withdrawal
    from app.services.audit_service import create_audit_entry
    from app.models.audit import AuditEventType

    await create_audit_entry(
        session,
        event_type=AuditEventType.WALLET_WITHDRAWAL,
        actor_id=player_id,
        details={"amount": str(amount), "balance_after": str(wallet.balance)},
        ip_address=ip_address,
    )

    return transaction


async def debit(
    session: AsyncSession,
    player_id: UUID,
    amount: Decimal,
    round_id: UUID,
) -> Transaction:
    """Deduct bet amount from player wallet atomically.

    Uses SELECT ... FOR UPDATE for row-level locking and bumps the version
    column for optimistic concurrency control.

    Requirement 2.7: Atomic transaction to prevent double-spending.
    """
    result = await session.execute(
        select(Wallet).where(Wallet.player_id == player_id).with_for_update()
    )
    wallet = result.scalar_one()

    if wallet.balance < amount:
        raise InsufficientBalanceError(balance=wallet.balance, requested=amount)

    wallet.balance -= amount
    wallet.version += 1

    transaction = Transaction(
        wallet_id=wallet.id,
        player_id=player_id,
        type=TransactionType.BET_DEBIT,
        amount=amount,
        balance_after=wallet.balance,
        reference_id=round_id,
        description=f"Bet debit for round {round_id}",
    )
    session.add(transaction)

    await _invalidate_balance_cache(player_id)
    return transaction


async def credit(
    session: AsyncSession,
    player_id: UUID,
    amount: Decimal,
    round_id: UUID,
) -> Transaction:
    """Credit payout amount to player wallet atomically.

    Uses SELECT ... FOR UPDATE for row-level locking and bumps the version
    column for optimistic concurrency control.
    """
    result = await session.execute(
        select(Wallet).where(Wallet.player_id == player_id).with_for_update()
    )
    wallet = result.scalar_one()

    wallet.balance += amount
    wallet.version += 1

    transaction = Transaction(
        wallet_id=wallet.id,
        player_id=player_id,
        type=TransactionType.PAYOUT_CREDIT,
        amount=amount,
        balance_after=wallet.balance,
        reference_id=round_id,
        description=f"Payout credit for round {round_id}",
    )
    session.add(transaction)

    await _invalidate_balance_cache(player_id)
    return transaction


async def get_transactions(
    session: AsyncSession,
    player_id: UUID,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Return paginated transaction history sorted by created_at descending.

    Returns a dict with keys: transactions, page, page_size, total.

    Requirement 2.6: Paginated history, most recent first.
    """
    # Get wallet to find wallet_id
    wallet_result = await session.execute(
        select(Wallet).where(Wallet.player_id == player_id)
    )
    wallet = wallet_result.scalar_one_or_none()
    if wallet is None:
        return {"transactions": [], "page": page, "page_size": page_size, "total": 0}

    # Total count
    count_result = await session.execute(
        select(func.count()).select_from(Transaction).where(
            Transaction.wallet_id == wallet.id
        )
    )
    total = count_result.scalar_one()

    # Paginated query
    offset = (page - 1) * page_size
    txn_result = await session.execute(
        select(Transaction)
        .where(Transaction.wallet_id == wallet.id)
        .order_by(Transaction.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    transactions = list(txn_result.scalars().all())

    return {
        "transactions": transactions,
        "page": page,
        "page_size": page_size,
        "total": total,
    }
