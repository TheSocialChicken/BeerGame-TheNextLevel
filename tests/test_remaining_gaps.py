"""
Test skeletons for gaps not covered by existing test files.

Areas:
  A. WebSocket error paths (invalid JSON, zero-order, game-finished order)
  B. InMemoryGameStore edge cases (list_ids, overwrite, isolation)
  C. REST API phase guards and all-AI game
  D. OrderProcessor: zero-demand with existing backlog
  E. Classic app: scoreboard after round advance
  F. ConstantOrderAI: negative quantity must not produce negative output
"""

import json
import pytest

# ---------------------------------------------------------------------------
# A. WebSocket error paths
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
async def clear_store():
    from backend.services.game_store import game_store
    for gid in await game_store.list_ids():
        await game_store.delete(gid)
    yield
    for gid in await game_store.list_ids():
        await game_store.delete(gid)


async def _create_and_start(client, ai_roles=None):
    """Helper: create + start a game, return game_id."""
    payload = {} if ai_roles is None else {"ai_roles": ai_roles}
    resp = await client.post("/games/", json=payload)
    game_id = resp.json()["game_id"]
    await client.post(f"/games/{game_id}/start")
    return game_id


@pytest.mark.asyncio
async def test_websocket_invalid_json_no_crash():
    """Raw non-JSON text must not crash the server."""
    pytest.importorskip("httpx_ws")
    from httpx import AsyncClient, ASGITransport
    from httpx_ws import aconnect_ws
    from backend.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        game_id = await _create_and_start(client, ai_roles=[])

    async with aconnect_ws(f"ws://test/ws/{game_id}/retailer", app) as ws:
        await ws.receive_json()  # connected
        await ws.send_text("not_valid_json{{{{")
        # Server should either silently ignore or return an error event, never crash.
        # We just verify connection is still usable afterwards.
        await ws.send_json({"action": "get_state"})
        msg = await ws.receive_json()
        assert msg["event"] in ("state", "error")


@pytest.mark.asyncio
async def test_websocket_zero_quantity_order_accepted():
    """Order with quantity=0 is valid and should not return an error."""
    pytest.importorskip("httpx_ws")
    from httpx import AsyncClient, ASGITransport
    from httpx_ws import aconnect_ws
    from backend.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        game_id = await _create_and_start(
            client, ai_roles=["wholesaler", "distributor", "factory"]
        )

    async with aconnect_ws(f"ws://test/ws/{game_id}/retailer", app) as ws:
        await ws.receive_json()  # connected
        await ws.send_json({"action": "order", "quantity": 0})
        msg = await ws.receive_json()
        assert msg["event"] != "error", f"Zero-quantity order should be valid; got {msg}"


@pytest.mark.asyncio
async def test_websocket_order_missing_quantity_returns_error():
    """Action 'order' without a quantity field should return an error event."""
    pytest.importorskip("httpx_ws")
    from httpx import AsyncClient, ASGITransport
    from httpx_ws import aconnect_ws
    from backend.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        game_id = await _create_and_start(client, ai_roles=[])

    async with aconnect_ws(f"ws://test/ws/{game_id}/retailer", app) as ws:
        await ws.receive_json()  # connected
        await ws.send_json({"action": "order"})  # no quantity
        msg = await ws.receive_json()
        assert msg["event"] == "error"


@pytest.mark.asyncio
async def test_websocket_order_after_game_finished_returns_error():
    """Sending an order once the game has ended must return an error, not crash."""
    pytest.importorskip("httpx_ws")
    from httpx import AsyncClient, ASGITransport
    from httpx_ws import aconnect_ws
    from backend.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1-round all-AI game so it finishes quickly
        resp = await client.post(
            "/games/",
            json={"ai_roles": ["wholesaler", "distributor", "factory"],
                  "config": {"num_rounds": 1, "demand_pattern": [4]}},
        )
        game_id = resp.json()["game_id"]
        await client.post(f"/games/{game_id}/start")

    async with aconnect_ws(f"ws://test/ws/{game_id}/retailer", app) as ws:
        await ws.receive_json()  # connected
        await ws.send_json({"action": "order", "quantity": 4})
        # Drain events until game_over or order_accepted
        for _ in range(5):
            msg = await ws.receive_json()
            if msg["event"] in ("game_over", "round_complete"):
                break

        # Now try to order again after game ended
        await ws.send_json({"action": "order", "quantity": 4})
        msg = await ws.receive_json()
        assert msg["event"] == "error"


# ---------------------------------------------------------------------------
# B. InMemoryGameStore edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_game_store_list_ids_empty():
    from backend.services.game_store import InMemoryGameStore
    store = InMemoryGameStore()
    ids = await store.list_ids()
    assert ids == []


@pytest.mark.asyncio
async def test_game_store_list_ids_after_saves():
    from backend.services.game_store import InMemoryGameStore
    from core.engine.game_engine import GameEngine

    store = InMemoryGameStore()
    eng = GameEngine()
    s1 = eng.create_game()
    s2 = eng.create_game()
    await store.save(s1)
    await store.save(s2)
    ids = await store.list_ids()
    assert s1.game_id in ids
    assert s2.game_id in ids
    assert len(ids) == 2


@pytest.mark.asyncio
async def test_game_store_overwrite_same_id():
    """Saving the same game_id twice must keep the latest state."""
    from backend.services.game_store import InMemoryGameStore
    from core.engine.game_engine import GameEngine

    store = InMemoryGameStore()
    eng = GameEngine()
    state = eng.create_game()
    await store.save(state)

    state = eng.start_game(state)
    await store.save(state)  # overwrite

    retrieved = await store.get(state.game_id)
    assert retrieved is not None
    from core.models.game import GamePhase
    assert retrieved.phase == GamePhase.ACTIVE


@pytest.mark.asyncio
async def test_game_store_delete_removes_from_list_ids():
    from backend.services.game_store import InMemoryGameStore
    from core.engine.game_engine import GameEngine

    store = InMemoryGameStore()
    eng = GameEngine()
    state = eng.create_game()
    await store.save(state)
    await store.delete(state.game_id)

    ids = await store.list_ids()
    assert state.game_id not in ids
    assert await store.get(state.game_id) is None


# ---------------------------------------------------------------------------
# C. REST API phase guards and all-AI game
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    from httpx import AsyncClient, ASGITransport
    from backend.main import app
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_api_submit_order_before_start_returns_error(api_client):
    """Orders submitted when game is still WAITING must be rejected."""
    async with api_client as client:
        resp = await client.post("/games/", json={})
        game_id = resp.json()["game_id"]
        # Do NOT start the game
        resp = await client.post(
            f"/games/{game_id}/orders",
            json={"role": "retailer", "quantity": 4},
        )
        assert resp.status_code in (400, 409, 422)


@pytest.mark.asyncio
async def test_api_submit_order_after_finish_returns_error(api_client):
    """Orders submitted when game is FINISHED must be rejected."""
    async with api_client as client:
        resp = await client.post(
            "/games/",
            json={"ai_roles": ["wholesaler", "distributor", "factory"],
                  "config": {"num_rounds": 1, "demand_pattern": [4]}},
        )
        game_id = resp.json()["game_id"]
        await client.post(f"/games/{game_id}/start")

        # Retailer order finishes the 1-round game
        await client.post(
            f"/games/{game_id}/orders",
            json={"role": "retailer", "quantity": 4},
        )

        # Now try again
        resp = await client.post(
            f"/games/{game_id}/orders",
            json={"role": "retailer", "quantity": 4},
        )
        assert resp.status_code in (400, 409, 422)


@pytest.mark.asyncio
async def test_api_create_game_all_ai_roles(api_client):
    """All four roles as AI should create a valid game."""
    async with api_client as client:
        resp = await client.post(
            "/games/",
            json={"ai_roles": ["retailer", "wholesaler", "distributor", "factory"]},
        )
        assert resp.status_code in (200, 201)
        body = resp.json()
        assert "game_id" in body


@pytest.mark.asyncio
async def test_api_create_game_invalid_config_rejected(api_client):
    """Config with num_rounds=101 (above max) must be rejected."""
    async with api_client as client:
        resp = await client.post(
            "/games/",
            json={"config": {"num_rounds": 101}},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_api_submit_zero_quantity_order_accepted(api_client):
    """Quantity=0 is a valid order."""
    async with api_client as client:
        resp = await client.post("/games/", json={})
        game_id = resp.json()["game_id"]
        await client.post(f"/games/{game_id}/start")
        resp = await client.post(
            f"/games/{game_id}/orders",
            json={"role": "retailer", "quantity": 0},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# D. OrderProcessor: zero demand with existing backlog
# ---------------------------------------------------------------------------

def test_fulfill_orders_zero_demand_backlog_persists():
    """When customer demand=0 but backlog exists, backlog does not clear on its own."""
    from core.engine.order_processor import fulfill_orders
    from core.models import GameConfig, GamePhase, GameState, PlayerRole, PlayerState

    cfg = GameConfig(num_rounds=4, demand_pattern=[4, 4, 4, 4])
    players = {
        role: PlayerState(role=role, inventory=2, backlog=0)
        for role in PlayerRole
    }
    # Artificially set retailer backlog from a prior round
    players[PlayerRole.RETAILER].backlog = 5
    state = GameState(
        game_id="test", phase=GamePhase.ACTIVE, config=cfg, players=players
    )

    state = fulfill_orders(state, customer_demand=0)
    retailer = state.players[PlayerRole.RETAILER]

    # demand=0 but backlog=5; with inventory=2, should ship 2 and still owe 3
    assert retailer.backlog == 3
    assert retailer.inventory == 0


def test_fulfill_orders_backlog_cleared_when_sufficient_inventory():
    """When demand=0 and inventory > backlog, backlog clears completely."""
    from core.engine.order_processor import fulfill_orders
    from core.models import GameConfig, GamePhase, GameState, PlayerRole, PlayerState

    cfg = GameConfig(num_rounds=4, demand_pattern=[4, 4, 4, 4])
    players = {
        role: PlayerState(role=role, inventory=20, backlog=0)
        for role in PlayerRole
    }
    players[PlayerRole.RETAILER].backlog = 5
    state = GameState(
        game_id="test", phase=GamePhase.ACTIVE, config=cfg, players=players
    )

    state = fulfill_orders(state, customer_demand=0)
    retailer = state.players[PlayerRole.RETAILER]
    assert retailer.backlog == 0
    assert retailer.inventory == 15  # 20 - 5


# ---------------------------------------------------------------------------
# E. Classic app: scoreboard after round advance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classic_scoreboard_after_one_round():
    """Scoreboard endpoint should reflect costs after one completed round."""
    from httpx import AsyncClient, ASGITransport
    from variants.classic.app import app as classic_app

    async with AsyncClient(transport=ASGITransport(app=classic_app), base_url="http://test") as client:
        resp = await client.post("/sessions")
        assert resp.status_code == 200
        session_id = resp.json()["session_id"]

        # Play one round with all AI
        from backend.services.game_store import game_store
        state = await game_store.get(session_id)
        from core.engine.game_engine import GameEngine
        from core.models import PlayerRole
        from core.ai_players.rule_based import ConstantOrderAI

        eng = GameEngine()
        state = eng.start_game(state)
        for role in PlayerRole:
            state = eng.submit_order(state, role, ConstantOrderAI(role).decide_order(state))
        state = eng.process_round(state)
        await game_store.save(state)

        resp = await client.get(f"/sessions/{session_id}/scoreboard")
        assert resp.status_code == 200
        board = resp.json()
        assert board["round"] == 1
        assert sum(board["scores"].values()) >= 0


@pytest.mark.asyncio
async def test_classic_scoreboard_at_game_over():
    """Scoreboard returns phase=finished and correct round count after game ends."""
    from httpx import AsyncClient, ASGITransport
    from variants.classic.app import app as classic_app

    async with AsyncClient(transport=ASGITransport(app=classic_app), base_url="http://test") as client:
        resp = await client.post("/sessions")
        session_id = resp.json()["session_id"]

        from backend.services.game_store import game_store
        from core.engine.game_engine import GameEngine
        from core.models import GamePhase, PlayerRole
        from core.ai_players.rule_based import ConstantOrderAI

        eng = GameEngine()
        state = await game_store.get(session_id)
        state = eng.start_game(state)
        while state.phase == GamePhase.ACTIVE:
            for role in PlayerRole:
                state = eng.submit_order(
                    state, role, ConstantOrderAI(role).decide_order(state)
                )
            state = eng.process_round(state)
        await game_store.save(state)

        resp = await client.get(f"/sessions/{session_id}/scoreboard")
        assert resp.status_code == 200
        board = resp.json()
        assert board["phase"] == "finished"
        assert board["round"] == state.config.num_rounds


# ---------------------------------------------------------------------------
# F. ConstantOrderAI negative quantity must not produce negative output
# ---------------------------------------------------------------------------

def test_constant_order_ai_negative_qty_raises():
    """ConstantOrderAI must reject negative quantity at construction time."""
    from core.ai_players.rule_based import ConstantOrderAI
    from core.models import PlayerRole

    with pytest.raises(ValueError):
        ConstantOrderAI(role=PlayerRole.RETAILER, quantity=-1)
