"""Celery task for updating leaderboard rankings after round completion.

The ``update_leaderboards`` task is dispatched after a round enters the
RESULT phase and must complete within 10 seconds (Requirement 8.2).
"""

import asyncio
import logging
from uuid import UUID

from app.celery_app import celery_app
from app.models.base import celery_session, dispose_celery_engine
from app.services import leaderboard_service

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from synchronous Celery worker context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(dispose_celery_engine())
        loop.close()


async def _do_update(round_id_str: str) -> None:
    round_id = UUID(round_id_str)
    async with celery_session() as session:
        await leaderboard_service.update_rankings(session, round_id)


@celery_app.task(
    name="app.tasks.leaderboard_tasks.update_leaderboards",
    soft_time_limit=10,
    time_limit=15,
)
def update_leaderboards(round_id: str) -> None:
    """Update all leaderboard rankings after a round completes.

    Requirement 8.2: Rankings updated within 10 seconds of round completion.
    """
    logger.info("Updating leaderboards for round %s", round_id)
    _run_async(_do_update(round_id))
    logger.info("Leaderboard update complete for round %s", round_id)
