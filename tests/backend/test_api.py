import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.services.game_store import game_store
from core.models import PlayerRole


@pytest.fixture(autouse=True)
async def clear_store():
    """Wipe game store between tests."""
    for gid in await game_store.list_ids():
        await game_store.delete(gid)
    yield
    for gid in await game_store.list_ids():
        await game_store.delete(gid)


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def game_id(client):
    resp = await client.post("/games/", json={})
    assert resp.status_code == 201
    return resp.json()["game_id"]


@pytest.fixture
async def active_game_id(client, game_id):
    resp = await client.post(f"/games/{game_id}/start")
    assert resp.status_code == 200
    return game_id


# ── health ────────────────────────────────────────────────────────────────────

async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── create game ───────────────────────────────────────────────────────────────

async def test_create_game_default(client):
    resp = await client.post("/games/", json={})
    assert resp.status_code == 201
    data = resp.json()
    assert "game_id" in data
    assert data["phase"] == "waiting"


async def test_create_game_custom_config(client):
    resp = await client.post("/games/", json={"config": {"num_rounds": 10}})
    assert resp.status_code == 201
    assert resp.json()["config"]["num_rounds"] == 10


async def test_create_game_with_ai_roles(client):
    resp = await client.post("/games/", json={"ai_roles": ["retailer", "wholesaler"]})
    assert resp.status_code == 201


# ── start game ────────────────────────────────────────────────────────────────

async def test_start_game(client, game_id):
    resp = await client.post(f"/games/{game_id}/start")
    assert resp.status_code == 200
    assert resp.json()["phase"] == "active"


async def test_start_game_not_found(client):
    resp = await client.post("/games/nonexistent/start")
    assert resp.status_code == 404


async def test_start_game_already_started(client, active_game_id):
    resp = await client.post(f"/games/{active_game_id}/start")
    assert resp.status_code == 400


# ── submit order ──────────────────────────────────────────────────────────────

async def test_submit_order(client, active_game_id):
    resp = await client.post(
        f"/games/{active_game_id}/orders",
        json={"role": "retailer", "quantity": 4},
    )
    assert resp.status_code == 200


async def test_submit_order_negative(client, active_game_id):
    resp = await client.post(
        f"/games/{active_game_id}/orders",
        json={"role": "retailer", "quantity": -1},
    )
    assert resp.status_code == 422  # Pydantic validation


async def test_submit_order_game_not_found(client):
    resp = await client.post(
        "/games/nope/orders",
        json={"role": "retailer", "quantity": 4},
    )
    assert resp.status_code == 404


async def test_full_round_all_human(client, active_game_id):
    """Submit orders for all 4 roles — round should auto-advance."""
    for role in ["retailer", "wholesaler", "distributor", "factory"]:
        resp = await client.post(
            f"/games/{active_game_id}/orders",
            json={"role": role, "quantity": 4},
        )
        assert resp.status_code == 200

    resp = await client.get(f"/games/{active_game_id}/state")
    assert resp.json()["round"] == 1


# ── get state ─────────────────────────────────────────────────────────────────

async def test_get_state(client, active_game_id):
    resp = await client.get(f"/games/{active_game_id}/state")
    assert resp.status_code == 200
    assert resp.json()["phase"] == "active"


async def test_get_state_with_role(client, active_game_id):
    resp = await client.get(f"/games/{active_game_id}/state?role=retailer")
    assert resp.status_code == 200
    data = resp.json()
    assert "inventory" in data
    assert data["role"] == "retailer"


async def test_get_state_not_found(client):
    resp = await client.get("/games/nope/state")
    assert resp.status_code == 404


# ── list games ────────────────────────────────────────────────────────────────

async def test_list_games(client, game_id):
    resp = await client.get("/games/")
    assert resp.status_code == 200
    assert game_id in resp.json()["game_ids"]
