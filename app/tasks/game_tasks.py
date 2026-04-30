"""Celery tasks for game round lifecycle management.

The advance_game_round periodic task drives the round state machine:
  BETTING → RESOLUTION → RESULT → new round (≤5s delay)

After each transition, the new state is published to Redis pub/sub
channel `channel:round:{round_id}` so all FastAPI instances can
broadcast consistent updates to connected WebSocket clients.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy import select

from app.celery_app import celery_app
from app.config import settings
from app.models.base import async_session_factory
from app.models.game import GameMode, GameRound, RoundPhase
from app.services import game_engine
from app.services.bot_service import bot_service

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from synchronous Celery worker context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _publish_round_state(round_id: UUID, phase: str, extra: dict | None = None):
    """Publish a round state transition to Redis pub/sub.

    Channel: channel:round:{round_id}
    """
    payload = {
        "round_id": str(round_id),
        "phase": phase,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        payload.update(extra)

    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        channel = f"channel:round:{round_id}"
        await client.publish(channel, json.dumps(payload))
        logger.info("Published state %s to %s", phase, channel)
    finally:
        await client.aclose()


async def _advance_betting_rounds():
    """Find rounds whose betting timer has expired and resolve them."""
    now = datetime.now(timezone.utc)
    async with async_session_factory() as session:
        result = await session.execute(
            select(GameRound).where(
                GameRound.phase == RoundPhase.BETTING,
                GameRound.betting_ends_at <= now,
            )
        )
        rounds = result.scalars().all()

        for game_round in rounds:
            try:
                resolved = await game_engine.resolve_round(session, game_round.id)
                await session.commit()
                await _publish_round_state(
                    resolved.id,
                    RoundPhase.RESOLUTION.value,
                    {
                        "winning_color": resolved.winning_color,
                        "period_number": resolved.period_number,
                    },
                )
                logger.info("Resolved round %s", resolved.id)
            except Exception:
                await session.rollback()
                logger.exception("Failed to resolve round %s", game_round.id)


async def _advance_resolution_rounds():
    """Find rounds in RESOLUTION phase, finalize them, and auto-start new rounds."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(GameRound).where(GameRound.phase == RoundPhase.RESOLUTION)
        )
        rounds = result.scalars().all()

        for game_round in rounds:
            try:
                finalized = await game_engine.finalize_round(session, game_round.id)
                await session.commit()

                # Calculate bot payouts (not saved to DB, just for display)
                bot_payouts = bot_service.calculate_bot_payouts(
                    finalized.id,
                    finalized.winning_number,
                    finalized.winning_color,
                )

                # Convert bot payouts to display format
                bot_payout_data = [
                    {
                        "bot_name": bp.bot_name,
                        "amount": str(bp.amount),
                    }
                    for bp in bot_payouts
                ]

                await _publish_round_state(
                    finalized.id,
                    RoundPhase.RESULT.value,
                    {
                        "winning_color": finalized.winning_color,
                        "winning_number": finalized.winning_number,
                        "total_payouts": str(finalized.total_payouts),
                        "period_number": finalized.period_number,
                        "bot_winners": bot_payout_data,
                    },
                )
                logger.info("Finalized round %s with %d bot winners", finalized.id, len(bot_payouts))

                # Clear bot data for this round to free memory
                bot_service.clear_round_bots(finalized.id)

                # Auto-start a new round for the same game mode (≤5s delay).
                # The delay is handled by the periodic task interval; the new
                # round is created immediately so it's ready when the next
                # tick fires.
                new_round = await game_engine.start_round(session, finalized.game_mode_id)
                await session.commit()

                # Generate bot bets for the new round
                mode_result = await session.execute(
                    select(GameMode).where(GameMode.id == new_round.game_mode_id)
                )
                game_mode = mode_result.scalar_one()

                # Create odds map from game mode
                odds_map = {opt.color: opt.odds for opt in game_mode.odds}

                # Generate bot bets
                bot_bets = bot_service.generate_bots_for_round(new_round.id, odds_map)

                # Get bot stats for display
                bot_stats = bot_service.get_bot_stats_for_round(new_round.id)

                await _publish_round_state(
                    new_round.id,
                    RoundPhase.BETTING.value,
                    {
                        "game_mode_id": str(new_round.game_mode_id),
                        "period_number": new_round.period_number,
                        "bot_count": bot_stats["total_bots"],
                    },
                )
                logger.info(
                    "Started new round %s for game mode %s with %d bots",
                    new_round.id,
                    new_round.game_mode_id,
                    bot_stats["total_bots"],
                )
            except Exception:
                await session.rollback()
                logger.exception("Failed to finalize round %s", game_round.id)


@celery_app.task(name="app.tasks.game_tasks.advance_game_round")
def advance_game_round():
    """Periodic task that drives the round lifecycle.

    Called by Celery Beat on a short interval (e.g. every 2-5 seconds).
    1. Resolve BETTING rounds whose timer has expired.
    2. Finalize RESOLUTION rounds and auto-start new rounds.
    """
    _run_async(_advance_betting_rounds())
    _run_async(_advance_resolution_rounds())
