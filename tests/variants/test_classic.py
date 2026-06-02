import pytest
from httpx import AsyncClient, ASGITransport
from variants.classic.app import app
from variants.classic.config import get_classic_config, CLASSIC_CONFIG, CLASSIC_DESCRIPTION
from backend.services.game_store import game_store


@pytest.fixture(autouse=True)
async def clear_store():
    for gid in await game_store.list_ids():
        await game_store.delete(gid)
    yield
    for gid in await game_store.list_ids():
        await game_store.delete(gid)


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def test_classic_config_values():
    cfg = get_classic_config()
    assert cfg.num_rounds == 26
    assert cfg.initial_inventory == 12
    assert cfg.demand_pattern[:4] == [4, 4, 4, 4]
    assert cfg.demand_pattern[4:] == [8] * 22
    assert cfg.holding_cost == 0.5
    assert cfg.backlog_cost == 1.0
    assert cfg.shipping_delay == 2
    assert cfg.order_delay == 2


def test_get_classic_config_returns_copy():
    a = get_classic_config()
    b = get_classic_config()
    assert a is not b
    a.num_rounds = 99
    assert b.num_rounds == 26


def test_classic_description():
    assert isinstance(CLASSIC_DESCRIPTION, str)
    assert len(CLASSIC_DESCRIPTION) > 0


async def test_create_session(client):
    resp = await client.post("/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert "join_urls" in data
    assert set(data["join_urls"].keys()) == {"retailer", "wholesaler", "distributor", "factory"}


async def test_join_urls_format(client):
    resp = await client.post("/sessions")
    session_id = resp.json()["session_id"]
    urls = resp.json()["join_urls"]
    for role, url in urls.items():
        assert session_id in url
        assert role in url


async def test_scoreboard_not_found(client):
    resp = await client.get("/sessions/nonexistent/scoreboard")
    assert resp.status_code == 404


async def test_scoreboard_new_game(client):
    session_id = (await client.post("/sessions")).json()["session_id"]
    resp = await client.get(f"/sessions/{session_id}/scoreboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id
    assert data["round"] == 0
    assert data["phase"] == "waiting"
    assert set(data["scores"].keys()) == {"retailer", "wholesaler", "distributor", "factory"}
    assert data["demand_history"] == []
