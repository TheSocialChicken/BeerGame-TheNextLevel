"""
Integration tests for the Classic Beer Game FastAPI endpoints.

All tests use TestClient (ASGI transport) — no live server needed.
Each test is independent; fixtures in conftest.py provide a fresh client
and a ready game instance.
"""
import pytest
from fastapi.testclient import TestClient
from starlette.testclient import TestClient as StarletteTestClient

from variants.classic.main import app


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health_endpoint(client):
    """GET /health must return 200 and {"status": "ok"}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Game creation
# ---------------------------------------------------------------------------

def test_create_game(client):
    """POST /api/games returns a game object with required top-level fields."""
    response = client.post("/api/games", json={})
    assert response.status_code == 201
    body = response.json()
    assert "game_id" in body
    assert "round" in body
    assert "status" in body
    assert "players" in body
    assert body["status"] in ("waiting", "active")


def test_create_game_with_human_role(client):
    """The retailer role must have is_human=True when passed in human_roles."""
    response = client.post("/api/games", json={"human_roles": ["retailer"]})
    assert response.status_code == 201
    body = response.json()
    players = body["players"]
    assert players["retailer"]["is_human"] is True
    # Other roles should be AI-controlled
    for role in ("wholesaler", "distributor", "factory"):
        assert players[role]["is_human"] is False, (
            f"{role} should be AI-controlled when not in human_roles"
        )


def test_create_game_all_roles_present(client):
    """Every new game must contain all four supply-chain roles."""
    response = client.post("/api/games", json={})
    assert response.status_code == 201
    players = response.json()["players"]
    for role in ("retailer", "wholesaler", "distributor", "factory"):
        assert role in players, f"Role '{role}' missing from game players"


# ---------------------------------------------------------------------------
# Game retrieval
# ---------------------------------------------------------------------------

def test_get_game(client, active_game):
    """GET /api/games/{id} returns the same game that was created."""
    game_id = active_game["game_id"]
    response = client.get(f"/api/games/{game_id}")
    assert response.status_code == 200
    assert response.json()["game_id"] == game_id


def test_get_nonexistent_game(client):
    """GET /api/games/{nonexistent-id} must return 404."""
    response = client.get("/api/games/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Order submission
# ---------------------------------------------------------------------------

def test_submit_orders_advances_round(client, active_game):
    """POST /api/games/{id}/orders with the human player's order increments round."""
    game_id = active_game["game_id"]
    initial_round = active_game["round"]

    # Retailer is the only human role (set in the active_game fixture)
    response = client.post(
        f"/api/games/{game_id}/orders",
        json={"orders": {"retailer": 4}},
    )
    assert response.status_code == 200
    updated_game = response.json()
    assert updated_game["round"] == initial_round + 1, (
        "Round number must increment after a valid order submission"
    )


def test_submit_orders_requires_human_roles(client, active_game):
    """
    Omitting the human role's order should return 422 (validation error).
    AI roles must NOT be submitted by the client.
    """
    game_id = active_game["game_id"]

    # Submitting an order for an AI role only — retailer (human) is missing
    response = client.post(
        f"/api/games/{game_id}/orders",
        json={"orders": {"wholesaler": 4}},
    )
    assert response.status_code == 422, (
        "Should reject orders that don't include all required human roles"
    )


def test_submit_orders_for_nonexistent_game(client):
    """POST orders to a nonexistent game must return 404."""
    response = client.post(
        "/api/games/00000000-0000-0000-0000-000000000000/orders",
        json={"orders": {"retailer": 4}},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

def test_websocket_connection(active_game):
    """
    WS /ws/games/{id} must connect successfully and immediately send
    the current game state as a JSON message.
    """
    game_id = active_game["game_id"]

    with StarletteTestClient(app) as sc:
        with sc.websocket_connect(f"/ws/games/{game_id}") as ws:
            data = ws.receive_json()
            assert "game_id" in data, (
                "WebSocket initial message must contain game_id"
            )
            assert data["game_id"] == game_id
            assert "round" in data
            assert "players" in data
