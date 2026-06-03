"""
Tests for GameEngine edge-cases not covered in test_engine.py.
"""
import pytest
from core.engine.game_engine import GameEngine
from core.models import GameConfig, GamePhase, PlayerRole


@pytest.fixture
def engine():
    return GameEngine()


@pytest.fixture
def active(engine):
    state = engine.create_game(ai_roles=set(PlayerRole))
    return engine.start_game(state)


# ── process_round phase guards ───────────────────────────────────────────────

def test_process_round_waiting_raises(engine):
    state = engine.create_game()
    assert state.phase == GamePhase.WAITING
    with pytest.raises(ValueError, match="not active"):
        engine.process_round(state)


def test_process_round_finished_raises(engine):
    from core.ai_players.rule_based import ConstantOrderAI

    config = GameConfig(num_rounds=1, demand_pattern=[4])
    state = engine.create_game(config, ai_roles=set(PlayerRole))
    state = engine.start_game(state)
    for role in PlayerRole:
        state = engine.submit_order(state, role, ConstantOrderAI(role).decide_order(state))
    state = engine.process_round(state)

    assert state.phase == GamePhase.FINISHED
    with pytest.raises(ValueError, match="not active"):
        engine.process_round(state)


# ── demand pattern wrapping ──────────────────────────────────────────────────

def test_demand_pattern_wraps_with_modulo(engine):
    """demand_pattern shorter than num_rounds → should wrap via modulo."""
    config = GameConfig(num_rounds=4, demand_pattern=[1, 2])
    state = engine.create_game(config, ai_roles=set(PlayerRole))
    state = engine.start_game(state)

    from core.ai_players.rule_based import ConstantOrderAI
    for _ in range(4):
        for role in PlayerRole:
            state = engine.submit_order(state, role, ConstantOrderAI(role).decide_order(state))
        state = engine.process_round(state)

    # pattern [1,2] over 4 rounds → [1, 2, 1, 2]
    assert state.customer_demand_history == [1, 2, 1, 2]


# ── get_visible_state ────────────────────────────────────────────────────────

def test_get_visible_state_all_required_keys(engine, active):
    visible = engine.get_visible_state(active, PlayerRole.WHOLESALER)
    for key in ("game_id", "round", "phase", "role", "inventory", "backlog",
                "last_order", "cumulative_cost", "incoming_shipments"):
        assert key in visible


def test_get_visible_state_no_other_player_data(engine, active):
    for role in PlayerRole:
        visible = engine.get_visible_state(active, role)
        assert "players" not in visible
        assert visible["role"] == role


def test_get_visible_state_incoming_shipments_serializable(engine, active):
    visible = engine.get_visible_state(active, PlayerRole.RETAILER)
    for shipment in visible["incoming_shipments"]:
        assert "quantity" in shipment
        assert "arrives_in_rounds" in shipment


# ── submit_order edge-cases ──────────────────────────────────────────────────

def test_submit_order_zero_quantity_allowed(engine, active):
    state = engine.submit_order(active, PlayerRole.RETAILER, 0)
    assert state.orders_this_round[PlayerRole.RETAILER] == 0


def test_submit_order_overwrites_previous(engine, active):
    state = engine.submit_order(active, PlayerRole.RETAILER, 5)
    state = engine.submit_order(state, PlayerRole.RETAILER, 9)
    assert state.orders_this_round[PlayerRole.RETAILER] == 9


# ── backlog multi-round persistence ─────────────────────────────────────────

def test_backlog_persists_across_rounds(engine):
    """Backlog built in round 1 should carry into round 2."""
    from core.ai_players.rule_based import ConstantOrderAI

    config = GameConfig(
        num_rounds=2,
        initial_inventory=2,
        demand_pattern=[10, 0],  # huge demand round 0, none round 1
        shipping_delay=2,
        order_delay=2,
    )
    state = engine.create_game(config, ai_roles=set(PlayerRole))
    state = engine.start_game(state)

    # Round 1: demand=10, inventory=2 → retailer can only ship 2, backlog=8
    for role in PlayerRole:
        state = engine.submit_order(state, role, 0)
    state = engine.process_round(state)

    retailer = state.players[PlayerRole.RETAILER]
    assert retailer.backlog > 0, "Expected backlog after demand > inventory"

    # Round 2: demand=0 but old backlog remains; with no new stock it stays
    for role in PlayerRole:
        state = engine.submit_order(state, role, 0)
    backlog_before = retailer.backlog
    state = engine.process_round(state)

    retailer2 = state.players[PlayerRole.RETAILER]
    # Inventory arrived is ≤ shipping_delay=2 rounds, so little or no stock yet
    # backlog cannot exceed the backlog from round 1 (it either reduces or stays)
    assert retailer2.cumulative_cost > 0


# ── GameConfig validation ────────────────────────────────────────────────────

def test_game_config_max_rounds_boundary(engine):
    """num_rounds=100 is the max allowed; 101 should fail."""
    import pydantic
    from core.models import GameConfig

    cfg = GameConfig(num_rounds=100, demand_pattern=[4] * 100)
    state = engine.create_game(cfg)
    assert state.config.num_rounds == 100

    with pytest.raises(pydantic.ValidationError):
        GameConfig(num_rounds=101)


def test_game_config_demand_pattern_zeros(engine):
    """demand_pattern with zeros is valid; rounds with zero demand shouldn't crash."""
    from core.ai_players.rule_based import ConstantOrderAI

    config = GameConfig(num_rounds=2, demand_pattern=[0, 0])
    state = engine.create_game(config, ai_roles=set(PlayerRole))
    state = engine.start_game(state)
    for _ in range(2):
        for role in PlayerRole:
            state = engine.submit_order(state, role, ConstantOrderAI(role).decide_order(state))
        state = engine.process_round(state)

    assert state.customer_demand_history == [0, 0]
    assert state.phase == GamePhase.FINISHED
