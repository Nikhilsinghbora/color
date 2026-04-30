"""Celery tasks for platform maintenance.

Includes periodic reset of expired deposit limit counters
(daily/weekly/monthly) so that players' usage tracking stays current,
and cleanup of expired session data from Redis.

Requirements: 10.2, 13.6
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal

import redis.asyncio as aioredis
from sqlalchemy import select

from app.celery_app import celery_app
from app.config import settings
from app.models.base import celery_session, dispose_celery_engine
from app.models.responsible_gambling import DepositLimit
from app.services.responsible_gambling_service import _compute_reset_time, _ensure_aware

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from synchronous Celery worker context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(dispose_celery_engine())
        loop.close()


async def _reset_expired_deposit_limits() -> int:
    """Reset all deposit limits whose resets_at has passed.

    For each expired limit:
      1. Set current_usage back to 0.
      2. Compute the next resets_at based on the limit's period.

    Returns the number of limits that were reset.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    reset_count = 0

    async with celery_session() as session:
        result = await session.execute(
            select(DepositLimit).where(DepositLimit.resets_at <= now)
        )
        expired_limits = result.scalars().all()

        for limit in expired_limits:
            limit.current_usage = Decimal("0.00")
            limit.resets_at = _compute_reset_time(limit.period, now)
            reset_count += 1

        if reset_count:
            await session.commit()
            logger.info("Reset %d expired deposit limit(s)", reset_count)

    return reset_count


@celery_app.task(name="app.tasks.maintenance_tasks.reset_deposit_limits")
def reset_deposit_limits() -> int:
    """Periodic task that resets expired deposit limit counters.

    Queries all DepositLimit records where resets_at <= now,
    resets current_usage to 0, and computes the next resets_at
    based on the limit period (daily/weekly/monthly).
    """
    return _run_async(_reset_expired_deposit_limits())


async def _cleanup_expired_sessions() -> int:
    """Scan and remove expired session keys from Redis.

    Session keys follow the pattern ``player:*:session`` and have a
    30-minute TTL set at creation.  Keys that Redis has already expired
    are cleaned up automatically, but this task also removes any stale
    keys whose TTL has been lost (e.g. due to persistence issues) by
    checking the TTL and deleting keys with TTL <= 0 that are not
    persistent (-1 means no expiry was set, which shouldn't happen for
    sessions but we clean those up too).

    Returns the number of keys removed.
    """
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    removed = 0
    try:
        cursor = None
        while cursor != 0:
            cursor, keys = await client.scan(
                cursor=cursor or 0,
                match="player:*:session",
                count=200,
            )
            for key in keys:
                ttl = await client.ttl(key)
                # ttl == -2: key doesn't exist (race), -1: no expiry set, 0: about to expire
                if ttl == -1 or ttl == -2:
                    await client.delete(key)
                    removed += 1
    finally:
        await client.aclose()

    if removed:
        logger.info("Cleaned up %d expired/stale session key(s)", removed)
    return removed


@celery_app.task(name="app.tasks.maintenance_tasks.cleanup_expired_sessions")
def cleanup_expired_sessions() -> int:
    """Periodic task that removes expired session data from Redis.

    Runs every 5 minutes via Celery Beat.  Scans for ``player:*:session``
    keys that have lost their TTL or are otherwise stale.
    """
    return _run_async(_cleanup_expired_sessions())
