import pytest
from core.engine.game_engine import GameEngine
from core.models import GameConfig, GamePhase, PlayerRole, ROLE_ORDER


@pytest.fixture
def engine():
    return GameEngine()


@pytest.fixture
def all_ai_game(engine):
    state = engine.create_game(ai_roles=set(PlayerRole))
    return engine.start_game(state)


def test_create_game_default(engine):
    state = engine.create_game()
    assert state.phase == GamePhase.WAITING
    assert state.current_round == 0
    assert len(state.players) == 4
    assert all(role in state.players for role in PlayerRole)


def test_create_game_initial_inventory(engine):
    state = engine.create_game(GameConfig(initial_inventory=8))
    for ps in state.players.values():
        assert ps.inventory == 8


def test_start_game(engine):
    state = engine.create_game()
    state = engine.start_game(state)
    assert state.phase == GamePhase.ACTIVE


def test_submit_order(engine):
    state = engine.create_game()
    state = engine.start_game(state)
    state = engine.submit_order(state, PlayerRole.RETAILER, 4)
    assert state.orders_this_round[PlayerRole.RETAILER] == 4


def test_submit_order_inactive_game(engine):
    state = engine.create_game()
    with pytest.raises(ValueError, match="not active"):
        engine.submit_order(state, PlayerRole.RETAILER, 4)


def test_submit_order_negative(engine):
    state = engine.create_game()
    state = engine.start_game(state)
    with pytest.raises(ValueError, match="negative"):
        engine.submit_order(state, PlayerRole.RETAILER, -1)


def test_submit_order_invalid_role(engine):
    state = engine.create_game()
    state = engine.start_game(state)
    with pytest.raises((ValueError, KeyError)):
        engine.submit_order(state, "invalid_role", 4)  # type: ignore


def test_process_round_advances(engine, all_ai_game):
    from core.ai_players.rule_based import OrderUpToAI
    state = all_ai_game

    # Submit AI orders
    for role in PlayerRole:
        ai = OrderUpToAI(role)
        qty = ai.decide_order(state)
        state = engine.submit_order(state, role, qty)

    state = engine.process_round(state)
    assert state.current_round == 1
    assert len(state.customer_demand_history) == 1


def test_process_round_clears_orders(engine, all_ai_game):
    from core.ai_players.rule_based import OrderUpToAI
    state = all_ai_game
    for role in PlayerRole:
        state = engine.submit_order(state, role, OrderUpToAI(role).decide_order(state))
    state = engine.process_round(state)
    assert state.orders_this_round == {}


def test_full_game_all_ai(engine):
    """Run complete 26-round game with all AI players."""
    from core.ai_players.rule_based import OrderUpToAI

    config = GameConfig(num_rounds=26)
    state = engine.create_game(config, ai_roles=set(PlayerRole))
    state = engine.start_game(state)

    for _ in range(config.num_rounds):
        assert state.phase == GamePhase.ACTIVE
        for role in ROLE_ORDER:
            ai = OrderUpToAI(role)
            state = engine.submit_order(state, role, ai.decide_order(state))
        state = engine.process_round(state)

    assert state.phase == GamePhase.FINISHED
    assert state.current_round == 26
    assert len(state.customer_demand_history) == 26
    assert state.total_cost() > 0


def test_costs_accrue(engine, all_ai_game):
    from core.ai_players.rule_based import OrderUpToAI
    state = all_ai_game
    for role in PlayerRole:
        state = engine.submit_order(state, role, OrderUpToAI(role).decide_order(state))
    state = engine.process_round(state)
    assert all(ps.cumulative_cost > 0 for ps in state.players.values())


def test_get_visible_state_hides_others(engine, all_ai_game):
    state = all_ai_game
    visible = engine.get_visible_state(state, PlayerRole.RETAILER)
    assert "inventory" in visible
    assert "role" in visible
    assert visible["role"] == PlayerRole.RETAILER
    # Other players' inventory not exposed
    assert "players" not in visible


def test_demand_pattern_respected(engine):
    config = GameConfig(num_rounds=4, demand_pattern=[2, 4, 6, 8])
    state = engine.create_game(config, ai_roles=set(PlayerRole))
    state = engine.start_game(state)

    from core.ai_players.rule_based import ConstantOrderAI
    for _ in range(4):
        for role in PlayerRole:
            state = engine.submit_order(state, role, ConstantOrderAI(role).decide_order(state))
        state = engine.process_round(state)

    assert state.customer_demand_history == [2, 4, 6, 8]
