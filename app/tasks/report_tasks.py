"""Celery tasks for compliance report generation.

Generates daily compliance reports summarizing total wagering volume,
payout ratios, flagged game rounds, and responsible gambling trigger events.

Requirements: 11.5
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.celery_app import celery_app
from app.models.audit import AuditEventType, AuditTrail
from app.models.base import celery_session, dispose_celery_engine
from app.models.game import Bet, GameRound, Payout

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from synchronous Celery worker context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(dispose_celery_engine())
        loop.close()


async def _generate_daily_report() -> dict:
    """Generate a compliance report for the previous 24-hour period.

    The report covers midnight-to-midnight UTC of the previous day.

    Metrics:
      - total_wagering_volume: sum of all bet amounts
      - total_payouts: sum of all payout amounts
      - payout_ratio: total_payouts / total_wagering_volume (or 0 if no bets)
      - flagged_rounds: count of game rounds flagged for review
      - responsible_gambling_events: count of responsible gambling audit events
    """
    now = datetime.now(timezone.utc)
    report_end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    report_start = report_end - timedelta(days=1)

    async with celery_session() as session:
        # Total wagering volume
        bet_result = await session.execute(
            select(func.coalesce(func.sum(Bet.amount), Decimal("0.00"))).where(
                Bet.created_at >= report_start,
                Bet.created_at < report_end,
            )
        )
        total_wagering_volume = bet_result.scalar_one()

        # Total payouts
        payout_result = await session.execute(
            select(func.coalesce(func.sum(Payout.amount), Decimal("0.00"))).where(
                Payout.created_at >= report_start,
                Payout.created_at < report_end,
            )
        )
        total_payouts = payout_result.scalar_one()

        # Payout ratio
        if total_wagering_volume and total_wagering_volume > 0:
            payout_ratio = (total_payouts / total_wagering_volume).quantize(
                Decimal("0.0001")
            )
        else:
            payout_ratio = Decimal("0.0000")

        # Flagged game rounds
        flagged_result = await session.execute(
            select(func.count()).select_from(GameRound).where(
                GameRound.flagged_for_review.is_(True),
                GameRound.created_at >= report_start,
                GameRound.created_at < report_end,
            )
        )
        flagged_rounds = flagged_result.scalar_one()

        # Responsible gambling trigger events
        rg_result = await session.execute(
            select(func.count()).select_from(AuditTrail).where(
                AuditTrail.event_type == AuditEventType.RESPONSIBLE_GAMBLING,
                AuditTrail.created_at >= report_start,
                AuditTrail.created_at < report_end,
            )
        )
        responsible_gambling_events = rg_result.scalar_one()

    report = {
        "report_date": report_start.date().isoformat(),
        "period_start": report_start.isoformat(),
        "period_end": report_end.isoformat(),
        "total_wagering_volume": str(total_wagering_volume),
        "total_payouts": str(total_payouts),
        "payout_ratio": str(payout_ratio),
        "flagged_rounds": flagged_rounds,
        "responsible_gambling_events": responsible_gambling_events,
    }

    logger.info(
        "Daily compliance report for %s: "
        "wagering=%s, payouts=%s, ratio=%s, flagged=%d, rg_events=%d",
        report["report_date"],
        report["total_wagering_volume"],
        report["total_payouts"],
        report["payout_ratio"],
        flagged_rounds,
        responsible_gambling_events,
    )

    return report


@celery_app.task(name="app.tasks.report_tasks.generate_daily_report")
def generate_daily_report() -> dict:
    """Scheduled task that generates the daily compliance report.

    Intended to run daily at 00:00 UTC via Celery Beat.
    The beat schedule will be configured in task 18 (Celery configuration).

    Report includes:
      - Total wagering volume (sum of all bets)
      - Total payouts and payout ratio
      - Count of flagged game rounds
      - Count of responsible gambling trigger events
    """
    return _run_async(_generate_daily_report())
