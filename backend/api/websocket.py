from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.services.connection_manager import manager
from backend.services.game_store import game_store
from core.engine.game_engine import GameEngine
from core.models import PlayerRole

router = APIRouter(tags=["websocket"])
engine = GameEngine()


@router.websocket("/ws/{game_id}/{role}")
async def websocket_endpoint(websocket: WebSocket, game_id: str, role: str):
    try:
        player_role = PlayerRole(role)
    except ValueError:
        await websocket.close(code=4000, reason=f"Invalid role: {role}")
        return

    state = await game_store.get(game_id)
    if state is None:
        await websocket.close(code=4004, reason="Game not found")
        return

    await manager.connect(websocket, game_id, player_role)

    # Send initial state on connect
    visible = engine.get_visible_state(state, player_role)
    await websocket.send_json({"event": "connected", **visible})

    try:
        while True:
            # Clients can send {"action": "order", "quantity": N}
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "order":
                quantity = data.get("quantity", 0)
                state = await game_store.get(game_id)
                if state is None:
                    break
                try:
                    state = engine.submit_order(state, player_role, int(quantity))
                    await game_store.save(state)
                    await websocket.send_json(
                        {"event": "order_accepted", "quantity": quantity}
                    )

                    if state.is_round_complete():
                        from core.ai_players.rule_based import OrderUpToAI
                        for r, ps in state.players.items():
                            if ps.is_ai and r not in state.orders_this_round:
                                ai_qty = OrderUpToAI(r).decide_order(state)
                                state = engine.submit_order(state, r, ai_qty)
                        state = engine.process_round(state)
                        await game_store.save(state)

                        from core.models import GamePhase
                        event = "round_complete" if state.phase == GamePhase.ACTIVE else "game_over"
                        await manager.broadcast(game_id, {
                            "event": event,
                            "round": state.current_round,
                            "phase": state.phase,
                            "total_cost": state.total_cost(),
                        })

                except ValueError as e:
                    await websocket.send_json({"event": "error", "message": str(e)})

            elif action == "get_state":
                state = await game_store.get(game_id)
                if state:
                    visible = engine.get_visible_state(state, player_role)
                    await websocket.send_json({"event": "state", **visible})

    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(game_id, player_role)
