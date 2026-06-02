import pytest
from core.models import (
    GameConfig,
    GamePhase,
    GameState,
    PlayerRole,
    PlayerState,
    IncomingShipment,
)


def test_game_config_defaults():
    cfg = GameConfig()
    assert cfg.num_rounds == 26
    assert cfg.initial_inventory == 12
    assert len(cfg.demand_pattern) == 26


def test_game_config_custom():
    cfg = GameConfig(num_rounds=10, initial_inventory=8)
    assert cfg.num_rounds == 10
    assert cfg.initial_inventory == 8


def test_game_config_invalid():
    with pytest.raises(Exception):
        GameConfig(num_rounds=0)
    with pytest.raises(Exception):
        GameConfig(initial_inventory=-1)


def test_player_state_round_cost():
    ps = PlayerState(role=PlayerRole.RETAILER, inventory=10, backlog=2)
    # 10 * 0.5 + 2 * 1.0 = 7.0
    assert ps.round_cost() == 7.0


def test_player_state_zero_cost():
    ps = PlayerState(role=PlayerRole.RETAILER, inventory=0, backlog=0)
    assert ps.round_cost() == 0.0


def test_game_state_round_complete_all_ai():
    state = GameState(
        game_id="test",
        players={
            role: PlayerState(role=role, inventory=12, backlog=0, is_ai=True)
            for role in PlayerRole
        },
    )
    # All AI — no human orders needed
    assert state.is_round_complete()


def test_game_state_round_incomplete():
    state = GameState(
        game_id="test",
        players={
            PlayerRole.RETAILER: PlayerState(role=PlayerRole.RETAILER, inventory=12, backlog=0, is_ai=False),
            PlayerRole.WHOLESALER: PlayerState(role=PlayerRole.WHOLESALER, inventory=12, backlog=0, is_ai=True),
            PlayerRole.DISTRIBUTOR: PlayerState(role=PlayerRole.DISTRIBUTOR, inventory=12, backlog=0, is_ai=True),
            PlayerRole.FACTORY: PlayerState(role=PlayerRole.FACTORY, inventory=12, backlog=0, is_ai=True),
        },
    )
    assert not state.is_round_complete()
    state.orders_this_round[PlayerRole.RETAILER] = 4
    assert state.is_round_complete()


def test_game_state_total_cost():
    players = {
        role: PlayerState(role=role, inventory=0, backlog=0, cumulative_cost=10.0)
        for role in PlayerRole
    }
    state = GameState(game_id="test", players=players)
    assert state.total_cost() == 40.0
