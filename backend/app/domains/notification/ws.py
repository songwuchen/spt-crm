"""
WebSocket endpoint for real-time notifications.
Clients connect to /ws/notifications?token=<jwt> and receive JSON messages.
"""
import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import jwt, JWTError

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Global connection registry: user_id -> set of WebSocket connections
_connections: Dict[str, Set[WebSocket]] = {}


def _verify_ws_token(token: str) -> dict | None:
    """Verify JWT token for WebSocket connection. Returns payload or None."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


async def broadcast_to_user(user_id: str, event: str, data: dict):
    """Send a message to all WebSocket connections of a user."""
    conns = _connections.get(user_id)
    if not conns:
        return
    message = json.dumps({"event": event, "data": data}, ensure_ascii=False, default=str)
    dead = []
    for ws in conns:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        conns.discard(ws)


@router.websocket("/ws/notifications")
async def ws_notifications(websocket: WebSocket, token: str = Query(...)):
    payload = _verify_ws_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await websocket.accept()

    # Register connection
    if user_id not in _connections:
        _connections[user_id] = set()
    _connections[user_id].add(websocket)
    logger.info("WS connected: user=%s, total=%d", user_id, len(_connections[user_id]))

    try:
        while True:
            data = await websocket.receive_text()
            # Respond to heartbeat pings
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        # Unregister connection
        conns = _connections.get(user_id)
        if conns:
            conns.discard(websocket)
            if not conns:
                del _connections[user_id]
        logger.info("WS disconnected: user=%s", user_id)
