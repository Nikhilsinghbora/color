"""WebSocket connection manager with Redis pub/sub fan-out.

Manages per-player, per-round WebSocket connections and subscribes to
Redis pub/sub channels for horizontal scaling across multiple FastAPI
instances. Provides heartbeat monitoring and stale connection cleanup.

Requirements: 3.5, 3.7, 3.8, 9.3, 9.6, 13.1
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import WebSocket, WebSocketDisconnect

from app.config import settings
from app.services.game_engine import RoundState

logger = logging.getLogger(__name__)

# Heartbeat interval and stale threshold in seconds
HEARTBEAT_INTERVAL = 30
STALE_CONNECTION_TIMEOUT = 90


@dataclass
class ConnectionInfo:
    """Metadata for a tracked WebSocket connection."""

    websocket: WebSocket
    player_id: UUID
    round_id: UUID
    connected_at: float = field(default_factory=time.monotonic)
    last_pong: float = field(default_factory=time.monotonic)


class WebSocketManager:
    """Singleton manager for WebSocket connections and Redis pub/sub fan-out."""

    def __init__(self) -> None:
        # round_id -> {player_id -> ConnectionInfo}
        self._connections: dict[UUID, dict[UUID, ConnectionInfo]] = {}
        # player_id -> ConnectionInfo (for personal messages)
        self._player_connections: dict[UUID, ConnectionInfo] = {}
        # round_id -> asyncio.Task (Redis subscriber tasks)
        self._subscriber_tasks: dict[UUID, list[asyncio.Task]] = {}
        # Background heartbeat task
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background heartbeat loop."""
        if self._running:
            return
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("WebSocketManager started")

    async def shutdown(self) -> None:
        """Cancel all subscriber tasks and the heartbeat loop."""
        self._running = False
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        for tasks in self._subscriber_tasks.values():
            for task in tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
        self._subscriber_tasks.clear()
        self._connections.clear()
        self._player_connections.clear()
        logger.info("WebSocketManager shut down")

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    async def connect(
        self, websocket: WebSocket, player_id: UUID, round_id: UUID
    ) -> None:
        """Register a WebSocket connection for a player in a round.

        Accepts the WebSocket, stores the connection, ensures Redis
        pub/sub subscribers are running for the round's channels, and
        sends an initial ``round_state`` message so the client can
        render immediately (fixes single-player bug).

        Requirements: 9.2, 9.3, 10.1, 10.3
        """
        await websocket.accept()

        info = ConnectionInfo(
            websocket=websocket, player_id=player_id, round_id=round_id
        )

        # Register in round-level map
        if round_id not in self._connections:
            self._connections[round_id] = {}
        self._connections[round_id][player_id] = info

        # Register in player-level map (for personal messages)
        self._player_connections[player_id] = info

        # Ensure Redis subscribers are running for this round
        if round_id not in self._subscriber_tasks:
            self._subscriber_tasks[round_id] = [
                asyncio.create_task(
                    self._subscribe_channel(f"channel:round:{round_id}", round_id)
                ),
                asyncio.create_task(
                    self._subscribe_channel(f"channel:chat:{round_id}", round_id)
                ),
            ]

        logger.info(
            "Player %s connected to round %s (%d total in round)",
            player_id,
            round_id,
            len(self._connections[round_id]),
        )

        # Send initial round_state so the player can render immediately.
        # Errors are non-fatal: the player will receive state on the next
        # periodic broadcast.
        await self._send_initial_round_state(websocket, round_id)

    async def _send_initial_round_state(
        self, websocket: WebSocket, round_id: UUID
    ) -> None:
        """Fetch and send the current round state to a newly connected client.

        Uses a fresh database session to query the round, then sends a
        ``round_state`` message with phase, timer, total_players, and
        total_pool.  Any failure is logged and swallowed so the
        connection is not torn down.

        Requirements: 9.2, 9.3, 10.1, 10.3
        """
        try:
            from app.models.base import async_session_factory
            from app.services import game_engine
            from app.services.bot_service import bot_service

            async with async_session_factory() as session:
                state = await game_engine.get_round_state(session, round_id)

            total_players = self.get_round_connection_count(round_id)
            bot_stats = bot_service.get_bot_stats_for_round(round_id)

            now = datetime.now(timezone.utc)

            # Ensure betting_ends_at is timezone-aware
            betting_ends_at = state.betting_ends_at
            if betting_ends_at.tzinfo is None:
                betting_ends_at = betting_ends_at.replace(tzinfo=timezone.utc)

            remaining = (betting_ends_at - now).total_seconds()
            remaining_seconds = max(0, int(remaining))

            # Ensure resolved_at and completed_at are also timezone-aware
            resolved_at = state.resolved_at
            if resolved_at and resolved_at.tzinfo is None:
                resolved_at = resolved_at.replace(tzinfo=timezone.utc)

            completed_at = state.completed_at
            if completed_at and completed_at.tzinfo is None:
                completed_at = completed_at.replace(tzinfo=timezone.utc)

            payload = {
                "type": "round_state",
                "round_id": str(state.round_id),
                "game_mode_id": str(state.game_mode_id),
                "phase": state.phase.value if hasattr(state.phase, "value") else str(state.phase),
                "winning_color": state.winning_color,
                "total_bets": str(state.total_bets),
                "total_payouts": str(state.total_payouts),
                "betting_ends_at": betting_ends_at.isoformat(),
                "resolved_at": resolved_at.isoformat() if resolved_at else None,
                "completed_at": completed_at.isoformat() if completed_at else None,
                "timer": remaining_seconds,
                "total_players": total_players + bot_stats["total_bots"],
                "total_pool": str(state.total_bets + bot_stats["total_bet_amount"]),
                "period_number": state.period_number,
            }
            await websocket.send_json(payload)
        except Exception:
            logger.exception(
                "Failed to send initial round_state for round %s; "
                "player will receive state on next broadcast",
                round_id,
            )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection and clean up if the round is empty."""
        target_round_id: Optional[UUID] = None
        target_player_id: Optional[UUID] = None

        # Find the connection by websocket reference
        for round_id, players in self._connections.items():
            for player_id, info in players.items():
                if info.websocket is websocket:
                    target_round_id = round_id
                    target_player_id = player_id
                    break
            if target_player_id is not None:
                break

        if target_round_id is None or target_player_id is None:
            return

        # Remove from maps
        self._connections[target_round_id].pop(target_player_id, None)
        self._player_connections.pop(target_player_id, None)

        # If no more connections for this round, cancel subscribers
        if not self._connections[target_round_id]:
            del self._connections[target_round_id]
            await self._cancel_round_subscribers(target_round_id)

        logger.info(
            "Player %s disconnected from round %s", target_player_id, target_round_id
        )

    # ------------------------------------------------------------------
    # Broadcasting
    # ------------------------------------------------------------------

    async def broadcast_round_state(
        self, round_id: UUID, state: RoundState
    ) -> None:
        """Publish round state to Redis so all instances fan out to clients."""
        payload = {
            "type": "round_state",
            "round_id": str(state.round_id),
            "game_mode_id": str(state.game_mode_id),
            "phase": state.phase.value if hasattr(state.phase, "value") else str(state.phase),
            "winning_color": state.winning_color,
            "total_bets": str(state.total_bets),
            "total_payouts": str(state.total_payouts),
            "betting_ends_at": state.betting_ends_at.isoformat(),
            "resolved_at": state.resolved_at.isoformat() if state.resolved_at else None,
            "completed_at": state.completed_at.isoformat() if state.completed_at else None,
            "period_number": state.period_number,
        }
        await self._publish(f"channel:round:{round_id}", payload)

    async def broadcast_chat(
        self, round_id: UUID, message: dict
    ) -> None:
        """Publish a chat message to Redis for fan-out to all round clients."""
        payload = {"type": "chat", **message}
        await self._publish(f"channel:chat:{round_id}", payload)

    async def send_personal(self, player_id: UUID, message: dict) -> None:
        """Send a message directly to a specific player's WebSocket."""
        info = self._player_connections.get(player_id)
        if info is None:
            return
        try:
            await info.websocket.send_json(message)
        except Exception:
            logger.warning("Failed to send personal message to player %s", player_id)
            await self._remove_stale_connection(info)

    # ------------------------------------------------------------------
    # Redis pub/sub
    # ------------------------------------------------------------------

    async def _publish(self, channel: str, payload: dict) -> None:
        """Publish a JSON payload to a Redis pub/sub channel."""
        client: Optional[aioredis.Redis] = None
        try:
            client = aioredis.from_url(settings.redis_url, decode_responses=True)
            await client.publish(channel, json.dumps(payload))
        except Exception:
            logger.exception("Failed to publish to %s", channel)
        finally:
            if client:
                await client.aclose()

    async def _subscribe_channel(self, channel: str, round_id: UUID) -> None:
        """Subscribe to a Redis pub/sub channel and fan out messages locally."""
        client: Optional[aioredis.Redis] = None
        pubsub: Optional[aioredis.client.PubSub] = None
        try:
            client = aioredis.from_url(settings.redis_url, decode_responses=True)
            pubsub = client.pubsub()
            await pubsub.subscribe(channel)
            logger.info("Subscribed to %s", channel)

            while self._running:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message["type"] == "message":
                    data = message["data"]
                    await self._fan_out(round_id, data)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Subscriber error on %s", channel)
        finally:
            if pubsub:
                try:
                    await pubsub.unsubscribe(channel)
                    await pubsub.aclose()
                except Exception:
                    pass
            if client:
                try:
                    await client.aclose()
                except Exception:
                    pass

    async def _fan_out(self, round_id: UUID, raw_data: str) -> None:
        """Send a raw JSON string to all WebSocket clients in a round."""
        players = self._connections.get(round_id)
        if not players:
            return

        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON on pub/sub for round %s", round_id)
            return

        stale: list[ConnectionInfo] = []
        for info in list(players.values()):
            try:
                await info.websocket.send_json(data)
            except Exception:
                stale.append(info)

        for info in stale:
            await self._remove_stale_connection(info)

    # ------------------------------------------------------------------
    # Heartbeat and stale connection cleanup
    # ------------------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        """Periodically ping clients and remove stale connections."""
        try:
            while self._running:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await self._ping_all()
                await self._cleanup_stale()
        except asyncio.CancelledError:
            pass

    async def _ping_all(self) -> None:
        """Send a WebSocket ping to every connected client."""
        for players in list(self._connections.values()):
            for info in list(players.values()):
                try:
                    await info.websocket.send_json({"type": "ping"})
                except Exception:
                    pass

    async def _cleanup_stale(self) -> None:
        """Remove connections that haven't responded within the timeout."""
        now = time.monotonic()
        stale: list[ConnectionInfo] = []
        for players in list(self._connections.values()):
            for info in list(players.values()):
                if now - info.last_pong > STALE_CONNECTION_TIMEOUT:
                    stale.append(info)

        for info in stale:
            logger.info(
                "Removing stale connection for player %s in round %s",
                info.player_id,
                info.round_id,
            )
            await self._remove_stale_connection(info)

    def record_pong(self, websocket: WebSocket) -> None:
        """Update the last_pong timestamp when a pong/heartbeat is received."""
        for players in self._connections.values():
            for info in players.values():
                if info.websocket is websocket:
                    info.last_pong = time.monotonic()
                    return

    async def _remove_stale_connection(self, info: ConnectionInfo) -> None:
        """Safely close and remove a stale connection."""
        try:
            await info.websocket.close()
        except Exception:
            pass
        await self.disconnect(info.websocket)

    async def _cancel_round_subscribers(self, round_id: UUID) -> None:
        """Cancel Redis subscriber tasks for a round."""
        tasks = self._subscriber_tasks.pop(round_id, [])
        for task in tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    def get_round_connection_count(self, round_id: UUID) -> int:
        """Return the number of active connections for a round."""
        return len(self._connections.get(round_id, {}))

    def get_total_connection_count(self) -> int:
        """Return the total number of active WebSocket connections."""
        return sum(len(p) for p in self._connections.values())


# Module-level singleton
ws_manager = WebSocketManager()
