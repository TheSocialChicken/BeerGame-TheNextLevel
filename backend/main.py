from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.games import router as games_router
from backend.api.websocket import router as ws_router
from backend.services.game_store import game_store
from core.engine.game_engine import GameEngine
from core.models import PlayerRole
from variants.classic.config import get_classic_config

_engine = GameEngine()

app = FastAPI(
    title="BeerGame: The Next Level",
    version="0.1.0",
    description="Multi-variant Beer Game serious game platform",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten per-variant in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(games_router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/sessions")
async def create_session():
    """Create a classic game session — retailer is human, rest are AI."""
    config = get_classic_config()
    ai_roles = {PlayerRole.WHOLESALER, PlayerRole.DISTRIBUTOR, PlayerRole.FACTORY}
    state = _engine.create_game(config, ai_roles=ai_roles)
    await game_store.save(state)
    session_id = state.game_id
    join_urls = {role.value: f"/ws/{session_id}/{role.value}" for role in PlayerRole}
    return {"session_id": session_id, "join_urls": join_urls}
