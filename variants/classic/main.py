"""
Classic Beer Game — FastAPI application entry point.

Endpoints
---------
GET  /health
POST /api/games
GET  /api/games/{game_id}
POST /api/games/{game_id}/orders
WS   /ws/games/{game_id}

Run locally:
    uvicorn variants.classic.main:app --reload --host 0.0.0.0 --port 8000
"""

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.engine.game_loop import advance_round, create_game
from core.models.game import GameState


# ── In-memory store ────────────────────────────────────────────────────────────

_games: dict[str, GameState] = {}

# WebSocket connection registry: game_id → list of active WebSocket connections
_connections: dict[str, list[WebSocket]] = {}


# ── Pydantic request / response models ────────────────────────────────────────

class CreateGameRequest(BaseModel):
    human_roles: list[str] = []


class SubmitOrdersRequest(BaseModel):
    orders: dict[str, int]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_game(game_id: str) -> GameState:
    """Retrieve a game by ID or raise 404."""
    game = _games.get(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail=f"Game '{game_id}' not found")
    return game


async def _broadcast(game_id: str, state: GameState) -> None:
    """Send updated GameState JSON to all connected WebSocket clients."""
    sockets = _connections.get(game_id, [])
    if not sockets:
        return
    payload = state.model_dump_json()
    dead: list[WebSocket] = []
    for ws in sockets:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        sockets.remove(ws)


# ── App setup ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield  # nothing to initialise / teardown in local-dev mode


app = FastAPI(
    title="BeerGame Classic",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/api/games", response_model=GameState, status_code=201)
async def create_new_game(body: CreateGameRequest) -> GameState:
    """
    Create and return a new game.

    Body
    ----
    ```json
    { "human_roles": ["retailer"] }
    ```
    Omit ``human_roles`` (or pass ``[]``) for a fully AI game.
    """
    state = create_game(human_roles=body.human_roles)
    _games[state.game_id] = state
    _connections[state.game_id] = []
    return state


@app.get("/api/games/{game_id}", response_model=GameState)
async def get_game(game_id: str) -> GameState:
    """Return the current state of a game."""
    return _get_game(game_id)


@app.post("/api/games/{game_id}/orders", response_model=GameState)
async def submit_orders(game_id: str, body: SubmitOrdersRequest) -> GameState:
    """
    Submit human player orders for the current round and advance the game.

    Body
    ----
    ```json
    { "orders": { "retailer": 8 } }
    ```
    Only supply orders for roles that are marked ``is_human=true``.
    AI roles are computed automatically; missing human orders default to 0.

    The round is advanced immediately and the new state is broadcast to all
    connected WebSocket clients.
    """
    state = _get_game(game_id)
    if state.status == "complete":
        raise HTTPException(status_code=409, detail="Game is already complete")

    missing = [r for r, p in state.players.items() if p.is_human and r not in body.orders]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing orders for human roles: {missing}")

    new_state = advance_round(state, human_orders=body.orders)
    _games[game_id] = new_state

    await _broadcast(game_id, new_state)
    return new_state


# ── WebSocket ──────────────────────────────────────────────────────────────────

@app.websocket("/ws/games/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str) -> None:
    """
    Real-time game state stream.

    Connect to receive the current GameState as JSON on every state change.
    The server sends the full state immediately on connect, then after each
    ``/orders`` call.

    Message format: serialised ``GameState`` JSON object.
    """
    # Validate game exists before accepting
    if game_id not in _games:
        await websocket.close(code=4004)
        return

    await websocket.accept()

    if game_id not in _connections:
        _connections[game_id] = []
    _connections[game_id].append(websocket)

    # Send current state immediately on connect
    current = _games[game_id]
    await websocket.send_text(current.model_dump_json())

    try:
        # Keep the connection alive; we don't expect messages from clients
        # (orders go through the REST endpoint), but we handle pings/close gracefully.
        while True:
            data = await websocket.receive_text()
            # Echo ping/pong if client sends "ping"
            if data.strip().lower() == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        sockets = _connections.get(game_id, [])
        if websocket in sockets:
            sockets.remove(websocket)
