"""Unit tests for the advance_game_round Celery task."""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.game import GameRound, RoundPhase
from app.tasks.game_tasks import (
    _advance_betting_rounds,
    _advance_resolution_rounds,
    _publish_round_state,
    advance_game_round,
)


# ---------------------------------------------------------------------------
# _publish_round_state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_round_state_sends_to_correct_channel():
    """State transitions are published to channel:round:{round_id}."""
    round_id = uuid4()
    mock_client = AsyncMock()
    mock_client.publish = AsyncMock()
    mock_client.aclose = AsyncMock()

    with patch("app.tasks.game_tasks.aioredis") as mock_aioredis:
        mock_aioredis.from_url.return_value = mock_client

        await _publish_round_state(round_id, "resolution", {"winning_color": "red"})

        expected_channel = f"channel:round:{round_id}"
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        assert call_args[0][0] == expected_channel

        payload = json.loads(call_args[0][1])
        assert payload["round_id"] == str(round_id)
        assert payload["phase"] == "resolution"
        assert payload["winning_color"] == "red"
        assert "timestamp" in payload

        mock_client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_publish_round_state_closes_client_on_error():
    """Redis client is closed even when publish raises."""
    round_id = uuid4()
    mock_client = AsyncMock()
    mock_client.publish = AsyncMock(side_effect=RuntimeError("connection lost"))
    mock_client.aclose = AsyncMock()

    with patch("app.tasks.game_tasks.aioredis") as mock_aioredis:
        mock_aioredis.from_url.return_value = mock_client

        with pytest.raises(RuntimeError, match="connection lost"):
            await _publish_round_state(round_id, "result")

        mock_client.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# _advance_betting_rounds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_advance_betting_rounds_resolves_expired():
    """Rounds past their betting_ends_at are resolved and published."""
    round_id = uuid4()
    game_mode_id = uuid4()

    mock_round = MagicMock(spec=GameRound)
    mock_round.id = round_id
    mock_round.game_mode_id = game_mode_id
    mock_round.phase = RoundPhase.BETTING
    mock_round.betting_ends_at = datetime.now(timezone.utc) - timedelta(seconds=10)

    resolved_round = MagicMock(spec=GameRound)
    resolved_round.id = round_id
    resolved_round.winning_color = "blue"
    resolved_round.period_number = "20250429100000001"

    mock_session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_round]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.tasks.game_tasks.async_session_factory", return_value=mock_session_ctx),
        patch("app.tasks.game_tasks.game_engine") as mock_engine,
        patch("app.tasks.game_tasks._publish_round_state", new_callable=AsyncMock) as mock_publish,
    ):
        mock_engine.resolve_round = AsyncMock(return_value=resolved_round)

        await _advance_betting_rounds()

        mock_engine.resolve_round.assert_awaited_once_with(mock_session, round_id)
        mock_session.commit.assert_awaited_once()
        mock_publish.assert_awaited_once_with(
            round_id,
            RoundPhase.RESOLUTION.value,
            {"winning_color": "blue", "period_number": "20250429100000001"},
        )


@pytest.mark.asyncio
async def test_advance_betting_rounds_rolls_back_on_error():
    """If resolve_round fails, the session is rolled back."""
    round_id = uuid4()

    mock_round = MagicMock(spec=GameRound)
    mock_round.id = round_id

    mock_session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_round]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.rollback = AsyncMock()

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.tasks.game_tasks.async_session_factory", return_value=mock_session_ctx),
        patch("app.tasks.game_tasks.game_engine") as mock_engine,
        patch("app.tasks.game_tasks._publish_round_state", new_callable=AsyncMock),
    ):
        mock_engine.resolve_round = AsyncMock(side_effect=RuntimeError("db error"))

        await _advance_betting_rounds()

        mock_session.rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# _advance_resolution_rounds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_advance_resolution_rounds_finalizes_and_starts_new():
    """RESOLUTION rounds are finalized and a new round is auto-started."""
    round_id = uuid4()
    new_round_id = uuid4()
    game_mode_id = uuid4()

    mock_round = MagicMock(spec=GameRound)
    mock_round.id = round_id
    mock_round.phase = RoundPhase.RESOLUTION

    finalized_round = MagicMock(spec=GameRound)
    finalized_round.id = round_id
    finalized_round.game_mode_id = game_mode_id
    finalized_round.winning_color = "green"
    finalized_round.winning_number = 3
    finalized_round.total_payouts = Decimal("500.00")
    finalized_round.period_number = "20250429100000042"

    new_round = MagicMock(spec=GameRound)
    new_round.id = new_round_id
    new_round.game_mode_id = game_mode_id
    new_round.period_number = "20250429100000043"

    mock_session = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_round]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.tasks.game_tasks.async_session_factory", return_value=mock_session_ctx),
        patch("app.tasks.game_tasks.game_engine") as mock_engine,
        patch("app.tasks.game_tasks._publish_round_state", new_callable=AsyncMock) as mock_publish,
    ):
        mock_engine.finalize_round = AsyncMock(return_value=finalized_round)
        mock_engine.start_round = AsyncMock(return_value=new_round)

        await _advance_resolution_rounds()

        mock_engine.finalize_round.assert_awaited_once_with(mock_session, round_id)
        mock_engine.start_round.assert_awaited_once_with(mock_session, game_mode_id)
        assert mock_session.commit.await_count == 2

        # Two publishes: RESULT for finalized, BETTING for new round
        assert mock_publish.await_count == 2
        calls = mock_publish.call_args_list
        assert calls[0].args[1] == RoundPhase.RESULT.value
        # Verify winning_number and period_number are included in the RESULT payload
        result_extra = calls[0].args[2]
        assert result_extra["winning_color"] == "green"
        assert result_extra["winning_number"] == 3
        assert result_extra["total_payouts"] == "500.00"
        assert result_extra["period_number"] == "20250429100000042"
        assert calls[1].args[1] == RoundPhase.BETTING.value
        # Verify period_number is included in the new round BETTING payload
        betting_extra = calls[1].args[2]
        assert betting_extra["period_number"] == "20250429100000043"


# ---------------------------------------------------------------------------
# advance_game_round (sync Celery entry point)
# ---------------------------------------------------------------------------


def test_advance_game_round_calls_both_phases():
    """The Celery task drives both betting and resolution advancement."""
    with (
        patch("app.tasks.game_tasks._run_async") as mock_run,
    ):
        advance_game_round()
        assert mock_run.call_count == 2
