"""Tests for core.reporting.report_generator — data extraction only (no Quarto)."""

import pytest

from core.engine.game_engine import GameEngine
from core.models import GameConfig, PlayerRole
from core.reporting.report_generator import build_report_data


@pytest.fixture
def finished_state():
    engine = GameEngine()
    cfg = GameConfig(num_rounds=3, demand_pattern=[4, 4, 4])
    state = engine.create_game(cfg, ai_roles=set(PlayerRole))
    state = engine.start_game(state)
    for _ in range(3):
        for role in PlayerRole:
            state = engine.submit_order(state, role, 4)
    return state


def test_build_report_data_keys(finished_state):
    data = build_report_data(finished_state)
    assert "game_id" in data
    assert "rounds_played" in data
    assert "roles" in data
    assert "round_history" in data
    assert "final_costs" in data


def test_build_report_data_roles(finished_state):
    data = build_report_data(finished_state)
    assert set(data["roles"]) == {r.value for r in PlayerRole}


def test_build_report_data_round_history_length(finished_state):
    data = build_report_data(finished_state)
    assert data["rounds_played"] == len(data["round_history"])


def test_build_report_data_round_history_structure(finished_state):
    data = build_report_data(finished_state)
    for entry in data["round_history"]:
        assert "customer_demand" in entry
        assert "cumulative_cost" in entry
        assert "inventory" in entry
        assert "orders" in entry


def test_build_report_data_final_costs_non_negative(finished_state):
    data = build_report_data(finished_state)
    for cost in data["final_costs"].values():
        assert cost >= 0
