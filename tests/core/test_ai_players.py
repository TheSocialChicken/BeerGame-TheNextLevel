import pytest
from core.engine.game_engine import GameEngine
from core.ai_players.rule_based import OrderUpToAI, ConstantOrderAI
from core.models import PlayerRole, GameConfig


@pytest.fixture
def active_state():
    engine = GameEngine()
    state = engine.create_game(ai_roles=set(PlayerRole))
    return engine.start_game(state)


def test_order_up_to_non_negative(active_state):
    for role in PlayerRole:
        ai = OrderUpToAI(role)
        assert ai.decide_order(active_state) >= 0


def test_constant_order_ai(active_state):
    ai = ConstantOrderAI(PlayerRole.RETAILER, quantity=6)
    assert ai.decide_order(active_state) == 6


def test_constant_order_ai_default(active_state):
    ai = ConstantOrderAI(PlayerRole.RETAILER)
    assert ai.decide_order(active_state) == 4


def test_order_up_to_reduces_order_when_stocked(active_state):
    """High inventory → lower order."""
    state = active_state
    state.players[PlayerRole.RETAILER].inventory = 100
    ai = OrderUpToAI(PlayerRole.RETAILER)
    assert ai.decide_order(state) == 0


def test_order_up_to_increases_order_when_depleted(active_state):
    """Low inventory + backlog → higher order."""
    state = active_state
    state.players[PlayerRole.RETAILER].inventory = 0
    state.players[PlayerRole.RETAILER].backlog = 5
    ai = OrderUpToAI(PlayerRole.RETAILER)
    assert ai.decide_order(state) > 0
