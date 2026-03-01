"""WebSocket connection manager for real-time push notifications."""

import logging
import json
from typing import Dict, Set

from fastapi import WebSocket

logger = logging.getLogger("spt_crm.ws")


class ConnectionManager:
    """Manages per-user WebSocket connections."""

    def __init__(self):
        # user_id -> set of active WebSocket connections
        self._connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        if user_id not in self._connections:
            self._connections[user_id] = set()
        self._connections[user_id].add(ws)
        logger.info("WS connected: user=%s, total=%d", user_id, len(self._connections[user_id]))

    def disconnect(self, user_id: str, ws: WebSocket):
        conns = self._connections.get(user_id)
        if conns:
            conns.discard(ws)
            if not conns:
                del self._connections[user_id]
        logger.info("WS disconnected: user=%s", user_id)

    async def send_to_user(self, user_id: str, data: dict):
        """Send JSON message to all connections of a specific user."""
        conns = self._connections.get(user_id)
        if not conns:
            return
        message = json.dumps(data, ensure_ascii=False)
        dead = []
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            conns.discard(ws)
        if not conns:
            self._connections.pop(user_id, None)

    @property
    def online_count(self) -> int:
        return sum(len(v) for v in self._connections.values())


# Singleton instance
ws_manager = ConnectionManager()
