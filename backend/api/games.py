from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from core.engine.game_engine import GameEngine
from core.models import GameConfig, GamePhase, PlayerRole
from backend.services.game_store import game_store
from backend.services.connection_manager import manager

router = APIRouter(prefix="/games", tags=["games"])
engine = GameEngine()


class CreateGameRequest(BaseModel):
    config: GameConfig = Field(default_factory=GameConfig)
    ai_roles: list[PlayerRole] = Field(default_factory=list)


class SubmitOrderRequest(BaseModel):
    role: PlayerRole
    quantity: int = Field(ge=0)


@router.post("/", status_code=201)
async def create_game(body: CreateGameRequest):
    state = engine.create_game(body.config, set(body.ai_roles))
    await game_store.save(state)
    return {"game_id": state.game_id, "phase": state.phase, "config": state.config}


@router.post("/{game_id}/start")
async def start_game(game_id: str):
    state = await game_store.get(game_id)
    if state is None:
        raise HTTPException(404, "Game not found")
    if state.phase != GamePhase.WAITING:
        raise HTTPException(400, f"Game already {state.phase}")

    state = engine.start_game(state)
    await game_store.save(state)
    await manager.broadcast(game_id, {"event": "game_started", "round": state.current_round})
    return {"game_id": game_id, "phase": state.phase}


@router.post("/{game_id}/orders")
async def submit_order(game_id: str, body: SubmitOrderRequest):
    state = await game_store.get(game_id)
    if state is None:
        raise HTTPException(404, "Game not found")

    try:
        state = engine.submit_order(state, body.role, body.quantity)
    except ValueError as e:
        raise HTTPException(400, str(e))

    await game_store.save(state)

    # Notify the player their order was received
    await manager.send_to(
        game_id,
        body.role,
        {"event": "order_accepted", "role": body.role, "quantity": body.quantity},
    )

    # Auto-advance if all orders in (includes AI players)
    if state.is_round_complete():
        # Fill in AI orders before processing
        from core.ai_players.rule_based import OrderUpToAI
        for role, ps in state.players.items():
            if ps.is_ai and role not in state.orders_this_round:
                ai = OrderUpToAI(role)
                state = engine.submit_order(state, role, ai.decide_order(state))

        state = engine.process_round(state)
        await game_store.save(state)

        event = "round_complete" if state.phase == GamePhase.ACTIVE else "game_over"
        await manager.broadcast(
            game_id,
            {
                "event": event,
                "round": state.current_round,
                "phase": state.phase,
                "total_cost": state.total_cost(),
            },
        )

    return {"game_id": game_id, "round": state.current_round, "phase": state.phase}


@router.get("/{game_id}/state")
async def get_state(game_id: str, role: PlayerRole | None = None):
    state = await game_store.get(game_id)
    if state is None:
        raise HTTPException(404, "Game not found")

    if role:
        return engine.get_visible_state(state, role)

    return {
        "game_id": state.game_id,
        "phase": state.phase,
        "round": state.current_round,
        "total_cost": state.total_cost(),
        "connected_roles": manager.connected_roles(game_id),
    }


@router.get("/")
async def list_games():
    return {"game_ids": await game_store.list_ids()}
