"""WebSocket endpoint for real-time game updates and chat.

Provides WS /ws/game/{round_id} with JWT authentication via query parameter.

Requirements: 3.5, 3.7, 9.3, 13.1
"""

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.config import settings
from app.services.ws_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter()


def _authenticate_token(token: str) -> UUID:
    """Validate a JWT token and return the player_id.

    Raises ValueError if the token is invalid or not an access token.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise ValueError("Invalid token") from exc

    if payload.get("type") != "access":
        raise ValueError("Not an access token")

    sub = payload.get("sub")
    if sub is None:
        raise ValueError("Missing sub claim")

    return UUID(sub)


@router.websocket("/ws/game/{round_id}")
async def game_websocket(
    websocket: WebSocket,
    round_id: UUID,
    token: str = Query(...),
) -> None:
    """WebSocket endpoint for a game round.

    1. Authenticate via JWT in the ``token`` query parameter.
    2. Register the connection with the WebSocket manager.
    3. Enter a receive loop handling ``chat`` and ``pong`` messages.
    4. Clean up on disconnect.
    """
    # --- Authenticate ---
    try:
        player_id = _authenticate_token(token)
    except (ValueError, Exception):
        await websocket.close(code=4001, reason="Authentication failed")
        return

    # --- Connect ---
    await ws_manager.connect(websocket, player_id, round_id)

    # --- Receive loop ---
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")

            if msg_type == "chat":
                text = data.get("text", "")
                if text:
                    chat_message = {
                        "player_id": str(player_id),
                        "text": text,
                    }
                    await ws_manager.broadcast_chat(round_id, chat_message)

            elif msg_type == "pong":
                ws_manager.record_pong(websocket)

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception(
            "Unexpected error in WebSocket for player %s, round %s",
            player_id,
            round_id,
        )
    finally:
        await ws_manager.disconnect(websocket)
