import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from fastapi.testclient import TestClient
from variants.classic.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def active_game(client):
    response = client.post("/api/games", json={"human_roles": ["retailer"]})
    return response.json()
