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
from app.models.base import celery_session, dispose_celery_engine
from app.models.game import GameMode, GameRound, RoundPhase
from app.services import game_engine
from app.services.bot_service import bot_service

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from synchronous Celery worker context.

    Creates a fresh event loop, runs the coroutine, then disposes the
    Celery DB engine so connections don't leak across loop boundaries.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(dispose_celery_engine())
        loop.close()


async def _publish_round_state(round_id: UUID, phase: str, extra: dict | None = None):
    """Publish a round state transition to Redis pub/sub.

    Channel: channel:round:{round_id}
    """
    payload = {
        "type": "phase_change",
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


async def _publish_result_message(
    round_id: UUID, winning_color: str, winning_number: int, bot_winners: list
):
    """Publish result message with winning details and payouts.

    This is separate from phase_change to match the frontend's expected message format.
    """
    from app.models.payout import Payout

    # Fetch real player payouts from database
    async with celery_session() as session:
        result = await session.execute(
            select(Payout).where(Payout.round_id == round_id)
        )
        payouts = result.scalars().all()

        payout_data = [
            {
                "bet_id": str(payout.bet_id),
                "amount": str(payout.amount),
            }
            for payout in payouts
        ]

    payload = {
        "type": "result",
        "round_id": str(round_id),
        "winning_color": winning_color,
        "winning_number": winning_number,
        "payouts": payout_data,
        "bot_winners": bot_winners,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        channel = f"channel:round:{round_id}"
        await client.publish(channel, json.dumps(payload))
        logger.info("Published result for round %s: %s %d", round_id, winning_color, winning_number)
    finally:
        await client.aclose()


async def _publish_new_round(
    round_id: UUID,
    game_mode_id: UUID,
    period_number: str,
    timer: int,
    bot_count: int,
    previous_round_id: UUID | None = None,
):
    """Publish new_round message when a new round starts.

    The message is published to the **previous** round's channel (if provided)
    so that clients still connected to the old round receive it and can
    transition.  It is also published to the new round's own channel for
    any clients that have already reconnected.
    """
    payload = {
        "type": "new_round",
        "round_id": str(round_id),
        "game_mode_id": str(game_mode_id),
        "period_number": period_number,
        "timer": timer,
        "bot_count": bot_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        msg = json.dumps(payload)
        # Publish to the previous round's channel so existing clients get it
        if previous_round_id:
            old_channel = f"channel:round:{previous_round_id}"
            await client.publish(old_channel, msg)
            logger.info("Published new_round to old channel %s", old_channel)
        # Also publish to the new round's channel
        new_channel = f"channel:round:{round_id}"
        await client.publish(new_channel, msg)
        logger.info("Published new_round for %s with timer %d seconds", round_id, timer)
    finally:
        await client.aclose()


async def _advance_betting_rounds():
    """Find rounds whose betting timer has expired and resolve them."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    async with celery_session() as session:
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
    async with celery_session() as session:
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

                # First send phase change to RESULT
                await _publish_round_state(
                    finalized.id,
                    RoundPhase.RESULT.value,
                    {
                        "winning_color": finalized.winning_color,
                        "winning_number": finalized.winning_number,
                        "total_payouts": str(finalized.total_payouts),
                        "period_number": finalized.period_number,
                    },
                )

                # Then send a separate result message with player payouts
                await _publish_result_message(
                    finalized.id,
                    finalized.winning_color,
                    finalized.winning_number,
                    bot_payout_data,
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

                # Calculate initial timer for the new round
                now_utc = datetime.now(timezone.utc)
                betting_ends_at = new_round.betting_ends_at
                if betting_ends_at.tzinfo is None:
                    betting_ends_at = betting_ends_at.replace(tzinfo=timezone.utc)
                initial_timer = max(0, int((betting_ends_at - now_utc).total_seconds()))

                # Send new_round message to the OLD round's channel so
                # existing clients receive it and can transition.
                await _publish_new_round(
                    new_round.id,
                    new_round.game_mode_id,
                    new_round.period_number,
                    initial_timer,
                    bot_stats["total_bots"],
                    previous_round_id=finalized.id,
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


async def _broadcast_timer_ticks():
    """Broadcast timer_tick messages for all active BETTING rounds."""
    now = datetime.now(timezone.utc)
    async with celery_session() as session:
        result = await session.execute(
            select(GameRound).where(GameRound.phase == RoundPhase.BETTING)
        )
        rounds = result.scalars().all()

        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            for game_round in rounds:
                # Ensure betting_ends_at is timezone-aware
                betting_ends_at = game_round.betting_ends_at
                if betting_ends_at.tzinfo is None:
                    betting_ends_at = betting_ends_at.replace(tzinfo=timezone.utc)

                remaining = (betting_ends_at - now).total_seconds()
                remaining_seconds = max(0, int(remaining))

                payload = {
                    "type": "timer_tick",
                    "round_id": str(game_round.id),
                    "remaining": remaining_seconds,
                    "timestamp": now.isoformat(),
                }

                channel = f"channel:round:{game_round.id}"
                await client.publish(channel, json.dumps(payload))
        finally:
            await client.aclose()


@celery_app.task(name="app.tasks.game_tasks.broadcast_timer_updates")
def broadcast_timer_updates():
    """Periodic task that broadcasts timer_tick messages every second.

    This allows the frontend to update countdown timers in real-time.
    """
    _run_async(_broadcast_timer_ticks())


@celery_app.task(name="app.tasks.game_tasks.advance_game_round")
def advance_game_round():
    """Periodic task that drives the round lifecycle.

    Called by Celery Beat on a short interval (e.g. every 2-5 seconds).
    1. Resolve BETTING rounds whose timer has expired.
    2. Finalize RESOLUTION rounds and auto-start new rounds.
    """
    _run_async(_advance_betting_rounds())
    _run_async(_advance_resolution_rounds())
