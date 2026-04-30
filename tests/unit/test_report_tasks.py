"""Unit tests for the generate_daily_report Celery task."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks.report_tasks import _generate_daily_report, generate_daily_report


def _make_mock_session(wagering=Decimal("0.00"), payouts=Decimal("0.00"), flagged=0, rg_events=0):
    """Create a mock async session that returns the given aggregate values.

    The task executes 4 queries in order:
      1. SUM(Bet.amount) -> wagering
      2. SUM(Payout.amount) -> payouts
      3. COUNT(GameRound flagged) -> flagged
      4. COUNT(AuditTrail responsible_gambling) -> rg_events
    """
    results = [wagering, payouts, flagged, rg_events]
    call_count = {"i": 0}

    async def mock_execute(_query):
        idx = call_count["i"]
        call_count["i"] += 1
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = results[idx]
        return mock_result

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=mock_execute)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx


@pytest.mark.asyncio
async def test_report_with_activity():
    """Report correctly aggregates wagering, payouts, flagged rounds, and RG events."""
    mock_ctx = _make_mock_session(
        wagering=Decimal("10000.00"),
        payouts=Decimal("8500.00"),
        flagged=3,
        rg_events=7,
    )

    with patch("app.tasks.report_tasks.async_session_factory", return_value=mock_ctx):
        report = await _generate_daily_report()

    assert report["total_wagering_volume"] == "10000.00"
    assert report["total_payouts"] == "8500.00"
    assert report["payout_ratio"] == "0.8500"
    assert report["flagged_rounds"] == 3
    assert report["responsible_gambling_events"] == 7
    assert "report_date" in report
    assert "period_start" in report
    assert "period_end" in report


@pytest.mark.asyncio
async def test_report_no_activity():
    """Report handles zero activity gracefully with zero values."""
    mock_ctx = _make_mock_session()

    with patch("app.tasks.report_tasks.async_session_factory", return_value=mock_ctx):
        report = await _generate_daily_report()

    assert report["total_wagering_volume"] == "0.00"
    assert report["total_payouts"] == "0.00"
    assert report["payout_ratio"] == "0.0000"
    assert report["flagged_rounds"] == 0
    assert report["responsible_gambling_events"] == 0


@pytest.mark.asyncio
async def test_report_payout_ratio_calculation():
    """Payout ratio is computed as total_payouts / total_wagering_volume."""
    mock_ctx = _make_mock_session(
        wagering=Decimal("5000.00"),
        payouts=Decimal("6000.00"),
    )

    with patch("app.tasks.report_tasks.async_session_factory", return_value=mock_ctx):
        report = await _generate_daily_report()

    assert report["payout_ratio"] == "1.2000"


@pytest.mark.asyncio
async def test_report_period_covers_previous_day():
    """Report period_start and period_end span the previous midnight-to-midnight UTC."""
    mock_ctx = _make_mock_session()

    with patch("app.tasks.report_tasks.async_session_factory", return_value=mock_ctx):
        report = await _generate_daily_report()

    start = datetime.fromisoformat(report["period_start"])
    end = datetime.fromisoformat(report["period_end"])

    assert start.hour == 0 and start.minute == 0 and start.second == 0
    assert end.hour == 0 and end.minute == 0 and end.second == 0
    assert (end - start).days == 1


def test_generate_daily_report_celery_entry_point():
    """The sync Celery task delegates to the async implementation."""
    with patch("app.tasks.report_tasks._run_async") as mock_run:
        mock_run.return_value = {"report_date": "2024-01-01"}
        result = generate_daily_report()
        assert result == {"report_date": "2024-01-01"}
        mock_run.assert_called_once()
