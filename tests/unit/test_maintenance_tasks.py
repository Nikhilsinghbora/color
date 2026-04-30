"""Unit tests for the reset_deposit_limits Celery maintenance task."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.responsible_gambling import DepositLimit, LimitPeriod
from app.tasks.maintenance_tasks import _reset_expired_deposit_limits, reset_deposit_limits


def _make_limit(period: LimitPeriod, resets_at: datetime, usage: Decimal = Decimal("50.00")) -> MagicMock:
    """Create a mock DepositLimit with the given attributes."""
    limit = MagicMock(spec=DepositLimit)
    limit.period = period
    limit.resets_at = resets_at
    limit.current_usage = usage
    limit.amount = Decimal("100.00")
    limit.player_id = uuid4()
    return limit


@pytest.mark.asyncio
async def test_reset_expired_limits_resets_usage_and_computes_next():
    """Expired limits have current_usage zeroed and resets_at advanced."""
    now = datetime.now(timezone.utc)
    expired_limit = _make_limit(
        LimitPeriod.DAILY,
        resets_at=now - timedelta(hours=1),
        usage=Decimal("75.00"),
    )

    mock_session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [expired_limit]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tasks.maintenance_tasks.async_session_factory", return_value=mock_ctx):
        count = await _reset_expired_deposit_limits()

    assert count == 1
    assert expired_limit.current_usage == Decimal("0.00")
    # resets_at should have been updated to a future time
    assert expired_limit.resets_at > now
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_reset_no_expired_limits_skips_commit():
    """When no limits are expired, commit is not called."""
    mock_session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tasks.maintenance_tasks.async_session_factory", return_value=mock_ctx):
        count = await _reset_expired_deposit_limits()

    assert count == 0
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_reset_multiple_periods():
    """Daily, weekly, and monthly limits are all reset correctly."""
    now = datetime.now(timezone.utc)
    limits = [
        _make_limit(LimitPeriod.DAILY, resets_at=now - timedelta(hours=2)),
        _make_limit(LimitPeriod.WEEKLY, resets_at=now - timedelta(days=1)),
        _make_limit(LimitPeriod.MONTHLY, resets_at=now - timedelta(days=5)),
    ]

    mock_session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = limits
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tasks.maintenance_tasks.async_session_factory", return_value=mock_ctx):
        count = await _reset_expired_deposit_limits()

    assert count == 3
    for limit in limits:
        assert limit.current_usage == Decimal("0.00")
        assert limit.resets_at > now


def test_reset_deposit_limits_celery_entry_point():
    """The sync Celery task delegates to the async implementation."""
    with patch("app.tasks.maintenance_tasks._run_async") as mock_run:
        mock_run.return_value = 2
        result = reset_deposit_limits()
        assert result == 2
        mock_run.assert_called_once()
