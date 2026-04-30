"""Property-based tests for WebSocket connection count accuracy.

# Feature: casino-ui-redesign, Property 6: WebSocket connection count accuracy
# For any sequence of connect/disconnect operations on the WS_Manager for a
# given round, get_round_connection_count(round_id) SHALL return the number of
# currently active (connected and not yet disconnected) unique players for
# that round.
# Validates: Requirements 10.3
"""

from enum import Enum
from dataclasses import dataclass
from typing import List
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    initialize,
    rule,
    invariant,
)

from app.services.ws_manager import WebSocketManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_ws() -> AsyncMock:
    """Create a unique mock WebSocket object."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


class OpType(Enum):
    CONNECT = "connect"
    DISCONNECT = "disconnect"


@dataclass
class ConnectOp:
    player_id: UUID
    round_id: UUID


@dataclass
class DisconnectOp:
    player_index: int  # index into the list of connected websockets


# Strategy: generate a pool of player IDs and round IDs, then a sequence of ops
st_player_id = st.builds(uuid4)
st_round_id = st.builds(uuid4)


# ---------------------------------------------------------------------------
# Feature: casino-ui-redesign, Property 6: WebSocket connection count accuracy
# Validates: Requirements 10.3
# ---------------------------------------------------------------------------


class TestProperty6WebSocketConnectionCountAccuracy:
    """**Validates: Requirements 10.3**"""

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[
            HealthCheck.function_scoped_fixture,
            HealthCheck.too_slow,
        ],
    )
    @given(
        num_players=st.integers(min_value=1, max_value=20),
        round_id=st_round_id,
    )
    @pytest.mark.asyncio
    async def test_connect_n_players_count_matches(self, num_players, round_id):
        """After connecting N unique players to a round,
        get_round_connection_count SHALL return N."""
        mgr = WebSocketManager()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock), \
             patch.object(mgr, "_send_initial_round_state", new_callable=AsyncMock):
            for _ in range(num_players):
                ws = _make_mock_ws()
                player_id = uuid4()
                await mgr.connect(ws, player_id, round_id)

        assert mgr.get_round_connection_count(round_id) == num_players

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[
            HealthCheck.function_scoped_fixture,
            HealthCheck.too_slow,
        ],
    )
    @given(
        num_players=st.integers(min_value=1, max_value=20),
        round_id=st_round_id,
    )
    @pytest.mark.asyncio
    async def test_connect_then_disconnect_all_count_zero(self, num_players, round_id):
        """After connecting N players then disconnecting all,
        get_round_connection_count SHALL return 0."""
        mgr = WebSocketManager()
        websockets = []

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock), \
             patch.object(mgr, "_send_initial_round_state", new_callable=AsyncMock):
            for _ in range(num_players):
                ws = _make_mock_ws()
                player_id = uuid4()
                await mgr.connect(ws, player_id, round_id)
                websockets.append(ws)

        for ws in websockets:
            await mgr.disconnect(ws)

        assert mgr.get_round_connection_count(round_id) == 0

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[
            HealthCheck.function_scoped_fixture,
            HealthCheck.too_slow,
        ],
    )
    @given(
        num_players=st.integers(min_value=2, max_value=20),
        disconnect_count=st.integers(min_value=1, max_value=19),
        round_id=st_round_id,
    )
    @pytest.mark.asyncio
    async def test_partial_disconnect_count_accurate(
        self, num_players, disconnect_count, round_id
    ):
        """After connecting N players and disconnecting K of them,
        get_round_connection_count SHALL return N - K."""
        # Ensure disconnect_count doesn't exceed num_players
        disconnect_count = min(disconnect_count, num_players - 1)

        mgr = WebSocketManager()
        websockets = []

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock), \
             patch.object(mgr, "_send_initial_round_state", new_callable=AsyncMock):
            for _ in range(num_players):
                ws = _make_mock_ws()
                player_id = uuid4()
                await mgr.connect(ws, player_id, round_id)
                websockets.append(ws)

        for ws in websockets[:disconnect_count]:
            await mgr.disconnect(ws)

        expected = num_players - disconnect_count
        assert mgr.get_round_connection_count(round_id) == expected

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[
            HealthCheck.function_scoped_fixture,
            HealthCheck.too_slow,
        ],
    )
    @given(
        ops=st.lists(
            st.tuples(
                st.sampled_from([OpType.CONNECT, OpType.DISCONNECT]),
                st.integers(min_value=0, max_value=49),
            ),
            min_size=1,
            max_size=50,
        ),
        round_id=st_round_id,
    )
    @pytest.mark.asyncio
    async def test_arbitrary_connect_disconnect_sequence(self, ops, round_id):
        """For any arbitrary sequence of connect/disconnect operations,
        get_round_connection_count SHALL return the number of currently
        active unique players."""
        mgr = WebSocketManager()
        # Track active connections: player_index -> (ws, player_id)
        active = {}
        next_player_idx = 0

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock), \
             patch.object(mgr, "_send_initial_round_state", new_callable=AsyncMock):
            for op_type, param in ops:
                if op_type == OpType.CONNECT:
                    ws = _make_mock_ws()
                    player_id = uuid4()
                    await mgr.connect(ws, player_id, round_id)
                    active[next_player_idx] = (ws, player_id)
                    next_player_idx += 1
                elif op_type == OpType.DISCONNECT and active:
                    # Pick a valid index to disconnect
                    keys = list(active.keys())
                    idx = keys[param % len(keys)]
                    ws, _ = active.pop(idx)
                    await mgr.disconnect(ws)

        assert mgr.get_round_connection_count(round_id) == len(active)

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[
            HealthCheck.function_scoped_fixture,
            HealthCheck.too_slow,
        ],
    )
    @given(
        round_ids=st.lists(st_round_id, min_size=2, max_size=5, unique=True),
        players_per_round=st.lists(
            st.integers(min_value=0, max_value=10), min_size=2, max_size=5
        ),
    )
    @pytest.mark.asyncio
    async def test_multiple_rounds_independent_counts(
        self, round_ids, players_per_round
    ):
        """Connection counts for different rounds SHALL be independent.
        Connecting players to one round SHALL NOT affect the count of
        another round."""
        # Align lengths
        count = min(len(round_ids), len(players_per_round))
        round_ids = round_ids[:count]
        players_per_round = players_per_round[:count]

        mgr = WebSocketManager()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock), \
             patch.object(mgr, "_send_initial_round_state", new_callable=AsyncMock):
            for rid, num in zip(round_ids, players_per_round):
                for _ in range(num):
                    ws = _make_mock_ws()
                    player_id = uuid4()
                    await mgr.connect(ws, player_id, rid)

        for rid, num in zip(round_ids, players_per_round):
            assert mgr.get_round_connection_count(rid) == num

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[
            HealthCheck.function_scoped_fixture,
            HealthCheck.too_slow,
        ],
    )
    @given(round_id=st_round_id)
    @pytest.mark.asyncio
    async def test_same_player_reconnect_replaces_connection(self, round_id):
        """If the same player_id connects twice to the same round,
        the count SHALL still be 1 (the second connection replaces the first)."""
        mgr = WebSocketManager()
        player_id = uuid4()
        ws1 = _make_mock_ws()
        ws2 = _make_mock_ws()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock), \
             patch.object(mgr, "_send_initial_round_state", new_callable=AsyncMock):
            await mgr.connect(ws1, player_id, round_id)
            await mgr.connect(ws2, player_id, round_id)

        assert mgr.get_round_connection_count(round_id) == 1

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[
            HealthCheck.function_scoped_fixture,
            HealthCheck.too_slow,
        ],
    )
    @given(round_id=st_round_id)
    @pytest.mark.asyncio
    async def test_disconnect_unknown_websocket_no_effect(self, round_id):
        """Disconnecting a WebSocket that was never connected SHALL NOT
        change the count for any round."""
        mgr = WebSocketManager()
        ws_connected = _make_mock_ws()
        ws_unknown = _make_mock_ws()
        player_id = uuid4()

        with patch.object(mgr, "_subscribe_channel", new_callable=AsyncMock), \
             patch.object(mgr, "_send_initial_round_state", new_callable=AsyncMock):
            await mgr.connect(ws_connected, player_id, round_id)

        await mgr.disconnect(ws_unknown)

        assert mgr.get_round_connection_count(round_id) == 1

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[
            HealthCheck.function_scoped_fixture,
            HealthCheck.too_slow,
        ],
    )
    @given(round_id=st_round_id)
    @pytest.mark.asyncio
    async def test_empty_round_count_zero(self, round_id):
        """A round with no connections SHALL have count 0."""
        mgr = WebSocketManager()
        assert mgr.get_round_connection_count(round_id) == 0
