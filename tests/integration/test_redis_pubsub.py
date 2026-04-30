"""Integration tests for Redis pub/sub message delivery.

Tests WebSocketManager pub/sub fan-out across simulated multi-instance
setup using mocked Redis connections.

Requirements: 3.8
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.game import RoundPhase
from app.services.game_engine import RoundState
from app.services.ws_manager import WebSocketManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_websocket():
    """Create a mock WebSocket that tracks sent messages."""
    ws = AsyncMock()
    ws.sent_messages = []

    async def _send_json(data):
        ws.sent_messages.append(data)

    ws.send_json = AsyncMock(side_effect=_send_json)
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    return ws


def _make_round_state(round_id=None, game_mode_id=None):
    """Create a RoundState for broadcast testing."""
    return RoundState(
        round_id=round_id or uuid4(),
        game_mode_id=game_mode_id or uuid4(),
        phase=RoundPhase.BETTING,
        winning_color=None,
        total_bets=Decimal("0.00"),
        total_payouts=Decimal("0.00"),
        betting_ends_at=datetime.now(timezone.utc) + timedelta(seconds=30),
        resolved_at=None,
        completed_at=None,
    )


# ===========================================================================
# 1. Pub/Sub Fan-Out Tests
# ===========================================================================


class TestPubSubFanOut:
    """Test Redis pub/sub message fan-out to WebSocket clients."""

    @pytest.mark.asyncio
    async def test_fan_out_delivers_to_all_clients_in_round(self):
        """Messages fan out to all clients connected to the same round."""
        mgr = WebSocketManager()
        mgr._publish = AsyncMock()
        mgr._subscribe_channel = AsyncMock()

        round_id = uuid4()
        ws1 = _make_mock_websocket()
        ws2 = _make_mock_websocket()
        ws3 = _make_mock_websocket()

        await mgr.connect(ws1, uuid4(), round_id)
        await mgr.connect(ws2, uuid4(), round_id)
        await mgr.connect(ws3, uuid4(), round_id)

        payload = json.dumps({"type": "round_state", "phase": "betting"})
        await mgr._fan_out(round_id, payload)

        for ws in [ws1, ws2, ws3]:
            assert len(ws.sent_messages) == 1
            assert ws.sent_messages[0]["type"] == "round_state"

    @pytest.mark.asyncio
    async def test_fan_out_isolates_rounds(self):
        """Messages for one round don't leak to clients in another round."""
        mgr = WebSocketManager()
        mgr._publish = AsyncMock()
        mgr._subscribe_channel = AsyncMock()

        round_a = uuid4()
        round_b = uuid4()
        ws_a = _make_mock_websocket()
        ws_b = _make_mock_websocket()

        await mgr.connect(ws_a, uuid4(), round_a)
        await mgr.connect(ws_b, uuid4(), round_b)

        payload = json.dumps({"type": "round_state", "phase": "resolution"})
        await mgr._fan_out(round_a, payload)

        assert len(ws_a.sent_messages) == 1
        assert len(ws_b.sent_messages) == 0

    @pytest.mark.asyncio
    async def test_fan_out_handles_invalid_json(self):
        """Invalid JSON on pub/sub channel is silently dropped."""
        mgr = WebSocketManager()
        mgr._publish = AsyncMock()
        mgr._subscribe_channel = AsyncMock()

        round_id = uuid4()
        ws = _make_mock_websocket()
        await mgr.connect(ws, uuid4(), round_id)

        await mgr._fan_out(round_id, "not-valid-json{{{")

        assert len(ws.sent_messages) == 0

    @pytest.mark.asyncio
    async def test_fan_out_removes_stale_connections(self):
        """Stale connections (send fails) are removed during fan-out."""
        mgr = WebSocketManager()
        mgr._publish = AsyncMock()
        mgr._subscribe_channel = AsyncMock()

        round_id = uuid4()
        ws_good = _make_mock_websocket()
        ws_bad = _make_mock_websocket()
        ws_bad.send_json = AsyncMock(side_effect=Exception("Connection closed"))

        player_good = uuid4()
        player_bad = uuid4()

        await mgr.connect(ws_good, player_good, round_id)
        await mgr.connect(ws_bad, player_bad, round_id)

        assert mgr.get_round_connection_count(round_id) == 2

        payload = json.dumps({"type": "test"})
        await mgr._fan_out(round_id, payload)

        # Stale connection should be removed
        assert mgr.get_round_connection_count(round_id) == 1


# ===========================================================================
# 2. Broadcast Round State via Publish
# ===========================================================================


class TestBroadcastRoundState:
    """Test broadcast_round_state publishes correct payload to Redis."""

    @pytest.mark.asyncio
    async def test_broadcast_round_state_publishes_to_correct_channel(self):
        """broadcast_round_state publishes to channel:round:{round_id}."""
        mgr = WebSocketManager()
        mgr._publish = AsyncMock()
        mgr._subscribe_channel = AsyncMock()

        round_id = uuid4()
        state = _make_round_state(round_id=round_id)

        await mgr.broadcast_round_state(round_id, state)

        mgr._publish.assert_called_once()
        channel = mgr._publish.call_args[0][0]
        payload = mgr._publish.call_args[0][1]

        assert channel == f"channel:round:{round_id}"
        assert payload["type"] == "round_state"
        assert payload["round_id"] == str(round_id)
        assert payload["phase"] == "betting"

    @pytest.mark.asyncio
    async def test_broadcast_chat_publishes_to_chat_channel(self):
        """broadcast_chat publishes to channel:chat:{round_id}."""
        mgr = WebSocketManager()
        mgr._publish = AsyncMock()
        mgr._subscribe_channel = AsyncMock()

        round_id = uuid4()
        message = {"player_id": str(uuid4()), "text": "hello"}

        await mgr.broadcast_chat(round_id, message)

        mgr._publish.assert_called_once()
        channel = mgr._publish.call_args[0][0]
        payload = mgr._publish.call_args[0][1]

        assert channel == f"channel:chat:{round_id}"
        assert payload["type"] == "chat"
        assert payload["text"] == "hello"


# ===========================================================================
# 3. Simulated Multi-Instance Delivery
# ===========================================================================


class TestMultiInstanceDelivery:
    """Simulate multiple FastAPI instances receiving the same pub/sub message."""

    @pytest.mark.asyncio
    async def test_same_message_delivered_across_instances(self):
        """Two manager instances both fan out the same message to their clients."""
        mgr1 = WebSocketManager()
        mgr1._publish = AsyncMock()
        mgr1._subscribe_channel = AsyncMock()

        mgr2 = WebSocketManager()
        mgr2._publish = AsyncMock()
        mgr2._subscribe_channel = AsyncMock()

        round_id = uuid4()
        ws1 = _make_mock_websocket()
        ws2 = _make_mock_websocket()

        await mgr1.connect(ws1, uuid4(), round_id)
        await mgr2.connect(ws2, uuid4(), round_id)

        # Simulate Redis delivering the same message to both instances
        payload = json.dumps({
            "type": "round_state",
            "round_id": str(round_id),
            "phase": "resolution",
            "winning_color": "red",
        })

        await mgr1._fan_out(round_id, payload)
        await mgr2._fan_out(round_id, payload)

        # Both clients received the message
        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 1
        assert ws1.sent_messages[0]["winning_color"] == "red"
        assert ws2.sent_messages[0]["winning_color"] == "red"

    @pytest.mark.asyncio
    async def test_personal_message_delivery(self):
        """send_personal delivers only to the target player."""
        mgr = WebSocketManager()
        mgr._publish = AsyncMock()
        mgr._subscribe_channel = AsyncMock()

        round_id = uuid4()
        player_a = uuid4()
        player_b = uuid4()
        ws_a = _make_mock_websocket()
        ws_b = _make_mock_websocket()

        await mgr.connect(ws_a, player_a, round_id)
        await mgr.connect(ws_b, player_b, round_id)

        await mgr.send_personal(player_a, {"type": "notification", "text": "for you"})

        assert len(ws_a.sent_messages) == 1
        assert ws_a.sent_messages[0]["text"] == "for you"
        assert len(ws_b.sent_messages) == 0


# ===========================================================================
# 4. Connection Lifecycle
# ===========================================================================


class TestConnectionLifecycle:
    """Test connection/disconnection and cleanup."""

    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self):
        """Disconnecting a WebSocket removes it from the manager."""
        mgr = WebSocketManager()
        mgr._publish = AsyncMock()
        mgr._subscribe_channel = AsyncMock()

        round_id = uuid4()
        ws = _make_mock_websocket()
        await mgr.connect(ws, uuid4(), round_id)

        assert mgr.get_total_connection_count() == 1

        await mgr.disconnect(ws)

        assert mgr.get_total_connection_count() == 0

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up_empty_round(self):
        """When last client disconnects, round entry is cleaned up."""
        mgr = WebSocketManager()
        mgr._publish = AsyncMock()
        mgr._subscribe_channel = AsyncMock()

        round_id = uuid4()
        ws = _make_mock_websocket()
        await mgr.connect(ws, uuid4(), round_id)
        await mgr.disconnect(ws)

        assert mgr.get_round_connection_count(round_id) == 0
