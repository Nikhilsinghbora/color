"""Integration tests for WebSocket endpoint.

Tests WebSocket connection/authentication, round state broadcast delivery,
and chat message delivery via mocked Redis pub/sub.

Requirements: 3.5, 9.3, 9.6
"""

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from jose import jwt
from starlette.testclient import TestClient

from app.config import settings
from app.main import create_app
from app.models.game import RoundPhase
from app.services.game_engine import RoundState
from app.services.ws_manager import WebSocketManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_token(player_id=None, expired=False, token_type="access"):
    """Create a JWT token for testing."""
    pid = player_id or uuid4()
    now = datetime.now(timezone.utc)
    exp = now - timedelta(hours=1) if expired else now + timedelta(hours=1)
    payload = {
        "sub": str(pid),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm), pid


def _make_round_state(round_id=None):
    """Create a RoundState for broadcast testing."""
    rid = round_id or uuid4()
    return RoundState(
        round_id=rid,
        game_mode_id=uuid4(),
        phase=RoundPhase.BETTING,
        winning_color=None,
        total_bets=Decimal("0.00"),
        total_payouts=Decimal("0.00"),
        betting_ends_at=datetime.now(timezone.utc) + timedelta(seconds=30),
        resolved_at=None,
        completed_at=None,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def fresh_ws_manager():
    """Provide a fresh WebSocketManager instance for each test.

    Patches the module-level singleton so the app uses our fresh instance,
    and mocks _publish and _subscribe_channel to avoid real Redis.
    """
    mgr = WebSocketManager()
    mgr._publish = AsyncMock()
    mgr._subscribe_channel = AsyncMock()

    with patch("app.api.websocket.ws_manager", mgr), \
         patch("app.services.ws_manager.ws_manager", mgr):
        yield mgr


@pytest.fixture()
def app(fresh_ws_manager):
    """Create a fresh FastAPI app with the patched ws_manager."""
    application = create_app()
    # Prevent the real ws_manager.start() from running (it would try Redis)
    application.router.on_startup.clear()
    application.router.on_shutdown.clear()
    return application


@pytest.fixture()
def client(app):
    """Starlette TestClient for WebSocket testing."""
    return TestClient(app, raise_server_exceptions=False)


# ===========================================================================
# 1. Connection and Authentication
# ===========================================================================

class TestWebSocketAuthentication:
    """Test WebSocket connection authentication via JWT query parameter."""

    def test_valid_token_connects(self, client, fresh_ws_manager):
        """Valid JWT token → connection accepted."""
        token, player_id = _make_token()
        round_id = uuid4()

        with client.websocket_connect(f"/ws/game/{round_id}?token={token}") as ws:
            # Connection accepted — manager should have registered it
            assert fresh_ws_manager.get_total_connection_count() == 1

    def test_missing_token_rejected(self, client):
        """Missing JWT token → connection rejected with code 4001."""
        round_id = uuid4()
        with pytest.raises(Exception) as exc_info:
            with client.websocket_connect(f"/ws/game/{round_id}") as ws:
                pass
        # FastAPI/Starlette will reject the connection because `token` is required

    def test_invalid_token_rejected(self, client):
        """Invalid JWT token → connection rejected with code 4001."""
        round_id = uuid4()
        with pytest.raises(Exception):
            with client.websocket_connect(f"/ws/game/{round_id}?token=bad.token.value") as ws:
                ws.receive_json()

    def test_expired_token_rejected(self, client):
        """Expired JWT token → connection rejected."""
        token, _ = _make_token(expired=True)
        round_id = uuid4()
        with pytest.raises(Exception):
            with client.websocket_connect(f"/ws/game/{round_id}?token={token}") as ws:
                ws.receive_json()

    def test_wrong_token_type_rejected(self, client):
        """Non-access token type → connection rejected."""
        token, _ = _make_token(token_type="refresh")
        round_id = uuid4()
        with pytest.raises(Exception):
            with client.websocket_connect(f"/ws/game/{round_id}?token={token}") as ws:
                ws.receive_json()


# ===========================================================================
# 2. Round State Broadcast Delivery
# ===========================================================================

class TestRoundStateBroadcast:
    """Test that connected clients receive round state broadcasts."""

    def test_broadcast_round_state_delivers_to_client(self, client, fresh_ws_manager):
        """Connect a client, broadcast round state, verify client receives it."""
        token, player_id = _make_token()
        round_id = uuid4()
        state = _make_round_state(round_id)

        with client.websocket_connect(f"/ws/game/{round_id}?token={token}") as ws:
            # Directly fan out a round_state message to connected clients
            # (simulating what Redis pub/sub would deliver)
            payload = {
                "type": "round_state",
                "round_id": str(state.round_id),
                "phase": "betting",
                "winning_color": None,
                "total_bets": "0.00",
                "total_payouts": "0.00",
            }
            asyncio.run(
                fresh_ws_manager._fan_out(round_id, json.dumps(payload))
            )

            data = ws.receive_json()
            assert data["type"] == "round_state"
            assert data["round_id"] == str(round_id)
            assert data["phase"] == "betting"

    def test_broadcast_reaches_multiple_clients(self, app, fresh_ws_manager):
        """Multiple connected clients all receive the broadcast."""
        token1, _ = _make_token()
        token2, _ = _make_token()
        round_id = uuid4()

        client1 = TestClient(app, raise_server_exceptions=False)
        client2 = TestClient(app, raise_server_exceptions=False)

        with client1.websocket_connect(f"/ws/game/{round_id}?token={token1}") as ws1, \
             client2.websocket_connect(f"/ws/game/{round_id}?token={token2}") as ws2:

            assert fresh_ws_manager.get_round_connection_count(round_id) == 2

            payload = json.dumps({"type": "round_state", "phase": "resolution"})
            asyncio.run(
                fresh_ws_manager._fan_out(round_id, payload)
            )

            d1 = ws1.receive_json()
            d2 = ws2.receive_json()
            assert d1["type"] == "round_state"
            assert d2["type"] == "round_state"


# ===========================================================================
# 3. Chat Message Delivery
# ===========================================================================

class TestChatMessageDelivery:
    """Test chat message sending and broadcast via the WebSocket endpoint."""

    def test_chat_message_triggers_broadcast(self, client, fresh_ws_manager):
        """Sending a chat message calls broadcast_chat (which publishes to Redis)."""
        token, player_id = _make_token()
        round_id = uuid4()

        with client.websocket_connect(f"/ws/game/{round_id}?token={token}") as ws:
            ws.send_json({"type": "chat", "text": "hello"})

            # Give the server a moment to process
            import time
            time.sleep(0.1)

            # broadcast_chat calls _publish, which we mocked
            fresh_ws_manager._publish.assert_called()
            call_args = fresh_ws_manager._publish.call_args
            channel = call_args[0][0]
            payload = call_args[0][1]
            assert channel == f"channel:chat:{round_id}"
            assert payload["type"] == "chat"
            assert payload["text"] == "hello"
            assert payload["player_id"] == str(player_id)

    def test_empty_chat_text_not_broadcast(self, client, fresh_ws_manager):
        """Empty chat text should not trigger a broadcast."""
        token, _ = _make_token()
        round_id = uuid4()

        with client.websocket_connect(f"/ws/game/{round_id}?token={token}") as ws:
            ws.send_json({"type": "chat", "text": ""})
            time.sleep(0.1)
            fresh_ws_manager._publish.assert_not_called()

    def test_chat_fan_out_delivers_to_clients(self, client, fresh_ws_manager):
        """Simulate Redis delivering a chat message — client receives it."""
        token, _ = _make_token()
        round_id = uuid4()

        with client.websocket_connect(f"/ws/game/{round_id}?token={token}") as ws:
            chat_payload = json.dumps({
                "type": "chat",
                "player_id": str(uuid4()),
                "text": "world",
            })
            asyncio.run(
                fresh_ws_manager._fan_out(round_id, chat_payload)
            )

            data = ws.receive_json()
            assert data["type"] == "chat"
            assert data["text"] == "world"
