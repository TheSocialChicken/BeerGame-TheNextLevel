import asyncio
import json
from fastapi import WebSocket
from core.models import PlayerRole


class ConnectionManager:
    """Manages WebSocket connections per game, broadcasts state updates."""

    def __init__(self):
        # game_id -> {role -> WebSocket}
        self._connections: dict[str, dict[str, WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, game_id: str, role: PlayerRole) -> None:
        await websocket.accept()
        async with self._lock:
            if game_id not in self._connections:
                self._connections[game_id] = {}
            self._connections[game_id][role.value] = websocket

    async def disconnect(self, game_id: str, role: PlayerRole) -> None:
        async with self._lock:
            if game_id in self._connections:
                self._connections[game_id].pop(role.value, None)
                if not self._connections[game_id]:
                    del self._connections[game_id]

    async def send_to(self, game_id: str, role: PlayerRole, payload: dict) -> None:
        ws = self._connections.get(game_id, {}).get(role.value)
        if ws:
            await ws.send_text(json.dumps(payload))

    async def broadcast(self, game_id: str, payload: dict) -> None:
        connections = dict(self._connections.get(game_id, {}))
        dead = []
        for role_key, ws in connections.items():
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(role_key)
        if dead:
            async with self._lock:
                for role_key in dead:
                    self._connections.get(game_id, {}).pop(role_key, None)

    def connected_roles(self, game_id: str) -> list[str]:
        return list(self._connections.get(game_id, {}).keys())


manager = ConnectionManager()
