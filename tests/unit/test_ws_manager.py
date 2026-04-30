"""Unit tests for the WebSocket manager service."""

import asyncio
import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio

from app.models.game import RoundPhase
from app.services.game_engine import RoundState
from app.services.ws_manager import (
    HEARTBEAT_INTERVAL,
    STALE_CONNECTION_TIMEOUT,
    ConnectionInfo,
    WebSocketManager,
)


def _make_ws(accepted: bool = True) -> AsyncMock:
    """Create a mock WebSocket."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


def _make_round_state(round_id=None, game_mode_id=None) -> RoundState:
    return RoundState(
        round_id=round_id or uuid4(),
        game_mode_id=game_mode_id or uuid4(),
        phase=RoundPhase.BETTING,
        winning_color=None,
        total_bets=Decimal("0.00"),
        total_payouts=Decimal("0.00"),
        betting_ends_at=datetime.now(timezone.utc),
        resolved_at=None,
        completed_at=None,
    )


class TestConnect:
    """Tests for WebSocketManager.connect."""

    @pytest.mark.asyncio
    async def test_accepts_websocket(self):
        mgr = WebSocketManager()
        ws = _make_ws()
        player_id, round_id = uuid4(), uuid4()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock), \
             patch.object(mgr, "_send_initial_round_state", new_callable=AsyncMock):
            await mgr.connect(ws, player_id, round_id)

        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_registers_connection_in_round(self):
        mgr = WebSocketManager()
        ws = _make_ws()
        player_id, round_id = uuid4(), uuid4()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock), \
             patch.object(mgr, "_send_initial_round_state", new_callable=AsyncMock):
            await mgr.connect(ws, player_id, round_id)

        assert mgr.get_round_connection_count(round_id) == 1
        assert mgr.get_total_connection_count() == 1

    @pytest.mark.asyncio
    async def test_registers_player_for_personal_messages(self):
        mgr = WebSocketManager()
        ws = _make_ws()
        player_id, round_id = uuid4(), uuid4()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock), \
             patch.object(mgr, "_send_initial_round_state", new_callable=AsyncMock):
            await mgr.connect(ws, player_id, round_id)

        assert player_id in mgr._player_connections

    @pytest.mark.asyncio
    async def test_multiple_players_same_round(self):
        mgr = WebSocketManager()
        round_id = uuid4()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock), \
             patch.object(mgr, "_send_initial_round_state", new_callable=AsyncMock):
            await mgr.connect(_make_ws(), uuid4(), round_id)
            await mgr.connect(_make_ws(), uuid4(), round_id)

        assert mgr.get_round_connection_count(round_id) == 2

    @pytest.mark.asyncio
    async def test_creates_subscriber_tasks_once_per_round(self):
        mgr = WebSocketManager()
        round_id = uuid4()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock) as mock_sub, \
             patch.object(mgr, "_send_initial_round_state", new_callable=AsyncMock):
            await mgr.connect(_make_ws(), uuid4(), round_id)
            first_call_count = mock_sub.call_count
            await mgr.connect(_make_ws(), uuid4(), round_id)
            # Should not create new subscribers for the same round
            assert mock_sub.call_count == first_call_count

    @pytest.mark.asyncio
    async def test_sends_initial_round_state_on_connect(self):
        """connect() calls _send_initial_round_state after registration."""
        mgr = WebSocketManager()
        ws = _make_ws()
        player_id, round_id = uuid4(), uuid4()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock), \
             patch.object(mgr, "_send_initial_round_state", new_callable=AsyncMock) as mock_init:
            await mgr.connect(ws, player_id, round_id)

        mock_init.assert_awaited_once_with(ws, round_id)


class TestSendInitialRoundState:
    """Tests for _send_initial_round_state."""

    @pytest.mark.asyncio
    async def test_sends_round_state_payload(self):
        """Sends a round_state message with phase, timer, total_players, total_pool."""
        mgr = WebSocketManager()
        ws = _make_ws()
        player_id, round_id = uuid4(), uuid4()

        # Register the connection so get_round_connection_count returns 1
        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock), \
             patch.object(mgr, "_send_initial_round_state", new_callable=AsyncMock):
            await mgr.connect(ws, player_id, round_id)

        state = _make_round_state(round_id=round_id)

        mock_session = AsyncMock()
        mock_factory_ctx = AsyncMock()
        mock_factory_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_factory_ctx)

        with patch("app.models.base.async_session_factory", mock_factory), \
             patch("app.services.game_engine.get_round_state", new=AsyncMock(return_value=state)):
            await mgr._send_initial_round_state(ws, round_id)

        ws.send_json.assert_awaited_once()
        payload = ws.send_json.call_args[0][0]
        assert payload["type"] == "round_state"
        assert payload["round_id"] == str(round_id)
        assert payload["phase"] == "betting"
        assert payload["total_players"] == 1
        assert "timer" in payload
        assert payload["timer"] >= 0
        assert "total_pool" in payload

    @pytest.mark.asyncio
    async def test_graceful_failure_on_db_error(self):
        """If fetching round state fails, the error is logged and swallowed."""
        mgr = WebSocketManager()
        ws = _make_ws()
        round_id = uuid4()

        with patch("app.models.base.async_session_factory", side_effect=Exception("DB down")):
            # Should not raise
            await mgr._send_initial_round_state(ws, round_id)

        ws.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_timer_clamped_to_zero_when_expired(self):
        """Timer remaining seconds should be 0 when betting_ends_at is in the past."""
        from datetime import timedelta

        mgr = WebSocketManager()
        ws = _make_ws()
        player_id, round_id = uuid4(), uuid4()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock), \
             patch.object(mgr, "_send_initial_round_state", new_callable=AsyncMock):
            await mgr.connect(ws, player_id, round_id)

        state = _make_round_state(round_id=round_id)
        state.betting_ends_at = datetime.now(timezone.utc) - timedelta(seconds=30)

        mock_session = AsyncMock()
        mock_factory_ctx = AsyncMock()
        mock_factory_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_factory_ctx)

        with patch("app.models.base.async_session_factory", mock_factory), \
             patch("app.services.game_engine.get_round_state", new=AsyncMock(return_value=state)):
            await mgr._send_initial_round_state(ws, round_id)

        payload = ws.send_json.call_args[0][0]
        assert payload["timer"] == 0


class TestDisconnect:
    """Tests for WebSocketManager.disconnect."""

    @pytest.mark.asyncio
    async def test_removes_connection(self):
        mgr = WebSocketManager()
        ws = _make_ws()
        player_id, round_id = uuid4(), uuid4()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock):
            await mgr.connect(ws, player_id, round_id)

        await mgr.disconnect(ws)
        assert mgr.get_round_connection_count(round_id) == 0
        assert player_id not in mgr._player_connections

    @pytest.mark.asyncio
    async def test_disconnect_unknown_websocket_is_noop(self):
        mgr = WebSocketManager()
        ws = _make_ws()
        await mgr.disconnect(ws)  # Should not raise

    @pytest.mark.asyncio
    async def test_cancels_subscribers_when_round_empty(self):
        mgr = WebSocketManager()
        ws = _make_ws()
        player_id, round_id = uuid4(), uuid4()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock):
            await mgr.connect(ws, player_id, round_id)

        with patch.object(mgr, "_cancel_round_subscribers", new_callable=AsyncMock) as mock_cancel:
            await mgr.disconnect(ws)
            mock_cancel.assert_awaited_once_with(round_id)

    @pytest.mark.asyncio
    async def test_keeps_subscribers_when_other_players_remain(self):
        mgr = WebSocketManager()
        ws1, ws2 = _make_ws(), _make_ws()
        round_id = uuid4()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock):
            await mgr.connect(ws1, uuid4(), round_id)
            await mgr.connect(ws2, uuid4(), round_id)

        with patch.object(mgr, "_cancel_round_subscribers", new_callable=AsyncMock) as mock_cancel:
            await mgr.disconnect(ws1)
            mock_cancel.assert_not_awaited()
            assert mgr.get_round_connection_count(round_id) == 1


class TestBroadcastRoundState:
    """Tests for broadcast_round_state."""

    @pytest.mark.asyncio
    async def test_publishes_to_redis(self):
        mgr = WebSocketManager()
        round_id = uuid4()
        state = _make_round_state(round_id=round_id)

        with patch.object(mgr, "_publish", new_callable=AsyncMock) as mock_pub:
            await mgr.broadcast_round_state(round_id, state)

        mock_pub.assert_awaited_once()
        channel, payload = mock_pub.call_args[0]
        assert channel == f"channel:round:{round_id}"
        assert payload["type"] == "round_state"
        assert payload["phase"] == "betting"


class TestBroadcastChat:
    """Tests for broadcast_chat."""

    @pytest.mark.asyncio
    async def test_publishes_chat_to_redis(self):
        mgr = WebSocketManager()
        round_id = uuid4()
        message = {"sender": "player1", "text": "hello"}

        with patch.object(mgr, "_publish", new_callable=AsyncMock) as mock_pub:
            await mgr.broadcast_chat(round_id, message)

        mock_pub.assert_awaited_once()
        channel, payload = mock_pub.call_args[0]
        assert channel == f"channel:chat:{round_id}"
        assert payload["type"] == "chat"
        assert payload["text"] == "hello"


class TestSendPersonal:
    """Tests for send_personal."""

    @pytest.mark.asyncio
    async def test_sends_to_connected_player(self):
        mgr = WebSocketManager()
        ws = _make_ws()
        player_id, round_id = uuid4(), uuid4()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock):
            await mgr.connect(ws, player_id, round_id)

        msg = {"type": "notification", "text": "You won!"}
        await mgr.send_personal(player_id, msg)
        ws.send_json.assert_awaited_with(msg)

    @pytest.mark.asyncio
    async def test_noop_for_unknown_player(self):
        mgr = WebSocketManager()
        await mgr.send_personal(uuid4(), {"type": "test"})  # Should not raise


class TestFanOut:
    """Tests for _fan_out."""

    @pytest.mark.asyncio
    async def test_sends_to_all_round_clients(self):
        mgr = WebSocketManager()
        round_id = uuid4()
        ws1, ws2 = _make_ws(), _make_ws()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock):
            await mgr.connect(ws1, uuid4(), round_id)
            await mgr.connect(ws2, uuid4(), round_id)

        data = json.dumps({"type": "round_state", "phase": "betting"})
        await mgr._fan_out(round_id, data)

        ws1.send_json.assert_awaited_once()
        ws2.send_json.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_removes_stale_on_send_failure(self):
        mgr = WebSocketManager()
        round_id = uuid4()
        ws = _make_ws()
        ws.send_json.side_effect = Exception("connection closed")

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock):
            await mgr.connect(ws, uuid4(), round_id)

        data = json.dumps({"type": "test"})
        await mgr._fan_out(round_id, data)

        assert mgr.get_round_connection_count(round_id) == 0

    @pytest.mark.asyncio
    async def test_ignores_invalid_json(self):
        mgr = WebSocketManager()
        round_id = uuid4()
        ws = _make_ws()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock):
            await mgr.connect(ws, uuid4(), round_id)

        await mgr._fan_out(round_id, "not-valid-json{{{")
        ws.send_json.assert_not_awaited()


class TestRecordPong:
    """Tests for record_pong."""

    @pytest.mark.asyncio
    async def test_updates_last_pong(self):
        mgr = WebSocketManager()
        ws = _make_ws()
        player_id, round_id = uuid4(), uuid4()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock):
            await mgr.connect(ws, player_id, round_id)

        info = mgr._connections[round_id][player_id]
        old_pong = info.last_pong

        # Simulate time passing
        await asyncio.sleep(0.01)
        mgr.record_pong(ws)

        assert info.last_pong > old_pong


class TestCleanupStale:
    """Tests for _cleanup_stale."""

    @pytest.mark.asyncio
    async def test_removes_stale_connections(self):
        mgr = WebSocketManager()
        ws = _make_ws()
        player_id, round_id = uuid4(), uuid4()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock):
            await mgr.connect(ws, player_id, round_id)

        # Artificially age the connection
        info = mgr._connections[round_id][player_id]
        info.last_pong = time.monotonic() - STALE_CONNECTION_TIMEOUT - 10

        await mgr._cleanup_stale()
        assert mgr.get_round_connection_count(round_id) == 0

    @pytest.mark.asyncio
    async def test_keeps_fresh_connections(self):
        mgr = WebSocketManager()
        ws = _make_ws()
        player_id, round_id = uuid4(), uuid4()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock):
            await mgr.connect(ws, player_id, round_id)

        await mgr._cleanup_stale()
        assert mgr.get_round_connection_count(round_id) == 1


class TestShutdown:
    """Tests for shutdown."""

    @pytest.mark.asyncio
    async def test_clears_all_state(self):
        mgr = WebSocketManager()
        ws = _make_ws()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock):
            await mgr.connect(ws, uuid4(), uuid4())

        await mgr.shutdown()
        assert mgr.get_total_connection_count() == 0
        assert len(mgr._subscriber_tasks) == 0
        assert len(mgr._player_connections) == 0


class TestIntrospection:
    """Tests for introspection helpers."""

    @pytest.mark.asyncio
    async def test_get_round_connection_count_empty(self):
        mgr = WebSocketManager()
        assert mgr.get_round_connection_count(uuid4()) == 0

    @pytest.mark.asyncio
    async def test_get_total_connection_count_multiple_rounds(self):
        mgr = WebSocketManager()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock):
            await mgr.connect(_make_ws(), uuid4(), uuid4())
            await mgr.connect(_make_ws(), uuid4(), uuid4())

        assert mgr.get_total_connection_count() == 2
