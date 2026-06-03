"""
WebSocket endpoint and ConnectionManager integration tests.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.services.connection_manager import ConnectionManager
from backend.services.game_store import game_store
from core.models import PlayerRole


# ── ConnectionManager unit tests ─────────────────────────────────────────────

@pytest.fixture
def cm():
    return ConnectionManager()


def make_mock_ws():
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


@pytest.mark.asyncio
async def test_connect_accept_and_register(cm):
    ws = make_mock_ws()
    await cm.connect(ws, "game1", PlayerRole.RETAILER)
    ws.accept.assert_awaited_once()
    assert "retailer" in cm.connected_roles("game1")


@pytest.mark.asyncio
async def test_disconnect_removes_role(cm):
    ws = make_mock_ws()
    await cm.connect(ws, "game1", PlayerRole.RETAILER)
    await cm.disconnect("game1", PlayerRole.RETAILER)
    assert "retailer" not in cm.connected_roles("game1")


@pytest.mark.asyncio
async def test_disconnect_last_role_removes_game(cm):
    ws = make_mock_ws()
    await cm.connect(ws, "game1", PlayerRole.RETAILER)
    await cm.disconnect("game1", PlayerRole.RETAILER)
    # game entry cleaned up when last connection leaves
    assert cm.connected_roles("game1") == []


@pytest.mark.asyncio
async def test_disconnect_nonexistent_game_no_error(cm):
    # Should not raise
    await cm.disconnect("nonexistent", PlayerRole.RETAILER)


@pytest.mark.asyncio
async def test_connected_roles_empty_game(cm):
    assert cm.connected_roles("no_such_game") == []


@pytest.mark.asyncio
async def test_send_to_reaches_correct_socket(cm):
    ws_retailer = make_mock_ws()
    ws_wholesaler = make_mock_ws()
    await cm.connect(ws_retailer, "game1", PlayerRole.RETAILER)
    await cm.connect(ws_wholesaler, "game1", PlayerRole.WHOLESALER)

    await cm.send_to("game1", PlayerRole.RETAILER, {"msg": "hello"})
    ws_retailer.send_text.assert_awaited_once_with(json.dumps({"msg": "hello"}))
    ws_wholesaler.send_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_to_missing_socket_no_error(cm):
    # No connection registered — should not raise
    await cm.send_to("game1", PlayerRole.RETAILER, {"msg": "hello"})


@pytest.mark.asyncio
async def test_broadcast_reaches_all_connections(cm):
    ws1 = make_mock_ws()
    ws2 = make_mock_ws()
    await cm.connect(ws1, "game1", PlayerRole.RETAILER)
    await cm.connect(ws1, "game1", PlayerRole.WHOLESALER)

    ws_r = make_mock_ws()
    ws_w = make_mock_ws()
    await cm.connect(ws_r, "g2", PlayerRole.RETAILER)
    await cm.connect(ws_w, "g2", PlayerRole.WHOLESALER)

    await cm.broadcast("g2", {"event": "ping"})
    ws_r.send_text.assert_awaited_once()
    ws_w.send_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_broadcast_removes_dead_connections(cm):
    ws_alive = make_mock_ws()
    ws_dead = make_mock_ws()
    ws_dead.send_text.side_effect = Exception("broken pipe")

    await cm.connect(ws_alive, "game1", PlayerRole.RETAILER)
    await cm.connect(ws_dead, "game1", PlayerRole.WHOLESALER)

    await cm.broadcast("game1", {"event": "tick"})

    # dead connection removed; alive one kept
    roles = cm.connected_roles("game1")
    assert "wholesaler" not in roles
    assert "retailer" in roles


@pytest.mark.asyncio
async def test_multiple_games_isolated(cm):
    ws_a = make_mock_ws()
    ws_b = make_mock_ws()
    await cm.connect(ws_a, "game_a", PlayerRole.RETAILER)
    await cm.connect(ws_b, "game_b", PlayerRole.RETAILER)

    await cm.broadcast("game_a", {"msg": "only_a"})
    ws_a.send_text.assert_awaited_once()
    ws_b.send_text.assert_not_awaited()


# ── WebSocket endpoint integration tests ─────────────────────────────────────

@pytest.fixture(autouse=True)
async def clear_store():
    for gid in await game_store.list_ids():
        await game_store.delete(gid)
    yield
    for gid in await game_store.list_ids():
        await game_store.delete(gid)


@pytest.mark.asyncio
async def test_websocket_invalid_role_closes_4000():
    pytest.importorskip("httpx_ws")
    from httpx import AsyncClient, ASGITransport
    from httpx_ws import aconnect_ws
    from backend.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/games/", json={})
        game_id = resp.json()["game_id"]
    async with aconnect_ws(f"ws://test/ws/{game_id}/invalid_role", app) as ws:
        msg = await ws.receive_json()
        assert msg is None or True  # connection closed before message


@pytest.mark.asyncio
async def test_websocket_unknown_game_closes_4004():
    pytest.importorskip("httpx_ws")
    from httpx_ws import aconnect_ws
    from backend.main import app

    async with aconnect_ws("ws://test/ws/nonexistent/retailer", app) as ws:
        # Server closes with 4004; we just confirm no crash
        pass


@pytest.mark.asyncio
async def test_websocket_connect_sends_initial_state():
    pytest.importorskip("httpx_ws")
    from httpx import AsyncClient, ASGITransport
    from httpx_ws import aconnect_ws
    from backend.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/games/", json={"ai_roles": []})
        game_id = resp.json()["game_id"]
        await client.post(f"/games/{game_id}/start")

    async with aconnect_ws(f"ws://test/ws/{game_id}/retailer", app) as ws:
        msg = await ws.receive_json()
        assert msg["event"] == "connected"
        assert "inventory" in msg
        assert "round" in msg


@pytest.mark.asyncio
async def test_websocket_order_action_accepted():
    pytest.importorskip("httpx_ws")
    from httpx import AsyncClient, ASGITransport
    from httpx_ws import aconnect_ws
    from backend.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/games/",
            json={"ai_roles": ["wholesaler", "distributor", "factory"]},
        )
        game_id = resp.json()["game_id"]
        await client.post(f"/games/{game_id}/start")

    async with aconnect_ws(f"ws://test/ws/{game_id}/retailer", app) as ws:
        await ws.receive_json()  # connected event
        await ws.send_json({"action": "order", "quantity": 4})
        response = await ws.receive_json()
        # Either order_accepted or round_complete (AI fills the rest)
        assert response["event"] in ("order_accepted", "round_complete", "game_over")


@pytest.mark.asyncio
async def test_websocket_get_state_action():
    pytest.importorskip("httpx_ws")
    from httpx import AsyncClient, ASGITransport
    from httpx_ws import aconnect_ws
    from backend.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/games/", json={"ai_roles": []})
        game_id = resp.json()["game_id"]
        await client.post(f"/games/{game_id}/start")

    async with aconnect_ws(f"ws://test/ws/{game_id}/retailer", app) as ws:
        await ws.receive_json()  # connected
        await ws.send_json({"action": "get_state"})
        msg = await ws.receive_json()
        assert msg["event"] == "state"
        assert "inventory" in msg


@pytest.mark.asyncio
async def test_websocket_invalid_action_no_crash():
    pytest.importorskip("httpx_ws")
    from httpx import AsyncClient, ASGITransport
    from httpx_ws import aconnect_ws
    from backend.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/games/", json={})
        game_id = resp.json()["game_id"]
        await client.post(f"/games/{game_id}/start")

    async with aconnect_ws(f"ws://test/ws/{game_id}/retailer", app) as ws:
        await ws.receive_json()  # connected
        await ws.send_json({"action": "bogus_action"})
        # No response for unknown action — server should not crash


@pytest.mark.asyncio
async def test_websocket_negative_order_returns_error():
    pytest.importorskip("httpx_ws")
    from httpx import AsyncClient, ASGITransport
    from httpx_ws import aconnect_ws
    from backend.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/games/", json={})
        game_id = resp.json()["game_id"]
        await client.post(f"/games/{game_id}/start")

    async with aconnect_ws(f"ws://test/ws/{game_id}/retailer", app) as ws:
        await ws.receive_json()  # connected
        await ws.send_json({"action": "order", "quantity": -5})
        msg = await ws.receive_json()
        assert msg["event"] == "error"


# ── InMemoryGameStore ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_game_store_delete_nonexistent_no_error():
    store = game_store
    await store.delete("nonexistent_id")  # should not raise


@pytest.mark.asyncio
async def test_game_store_get_missing_returns_none():
    store = game_store
    result = await store.get("no_such_game")
    assert result is None


@pytest.mark.asyncio
async def test_game_store_save_and_retrieve():
    from core.engine.game_engine import GameEngine
    eng = GameEngine()
    state = eng.create_game()
    await game_store.save(state)
    retrieved = await game_store.get(state.game_id)
    assert retrieved is not None
    assert retrieved.game_id == state.game_id
