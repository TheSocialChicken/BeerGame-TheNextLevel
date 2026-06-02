import asyncio

from core.models import GameState


class InMemoryGameStore:
    """Thread-safe in-memory store. Swap for Redis-backed store in production."""

    def __init__(self):
        self._games: dict[str, GameState] = {}
        self._lock = asyncio.Lock()

    async def get(self, game_id: str) -> GameState | None:
        return self._games.get(game_id)

    async def save(self, state: GameState) -> None:
        async with self._lock:
            self._games[state.game_id] = state

    async def delete(self, game_id: str) -> None:
        async with self._lock:
            self._games.pop(game_id, None)

    async def list_ids(self) -> list[str]:
        return list(self._games.keys())


game_store = InMemoryGameStore()
