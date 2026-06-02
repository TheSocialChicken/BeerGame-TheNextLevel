from fastapi import FastAPI, HTTPException
from core.engine.game_engine import GameEngine
from core.models import PlayerRole
from backend.api.games import router as games_router
from backend.api.websocket import router as websocket_router
from backend.services.game_store import game_store
from .config import get_classic_config

app = FastAPI(title="Classic Beer Game", version="0.1.0")
app.include_router(games_router)
app.include_router(websocket_router)

_engine = GameEngine()


@app.post("/sessions")
async def create_session() -> dict:
    config = get_classic_config()
    state = _engine.create_game(config, ai_roles=set())
    await game_store.save(state)
    session_id = state.game_id
    join_urls = {role.value: f"/ws/{session_id}/{role.value}" for role in PlayerRole}
    return {"session_id": session_id, "join_urls": join_urls}


@app.get("/sessions/{session_id}/scoreboard")
async def get_scoreboard(session_id: str) -> dict:
    state = await game_store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    scores = {
        role.value: state.players[role].cumulative_cost
        for role in PlayerRole
        if role in state.players
    }
    return {
        "session_id": state.game_id,
        "round": state.current_round,
        "phase": state.phase,
        "scores": scores,
        "demand_history": state.customer_demand_history,
    }
