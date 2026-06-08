"""
Unit tests for the Classic Beer Game engine.

These tests exercise core/engine directly without the HTTP layer.
All tests are independent — each creates its own game instance.
"""
import pytest

from core.engine.classic import ClassicGameEngine
from core.models.game import GameState, Role


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_engine() -> ClassicGameEngine:
    """Return a fresh engine with a new GameState."""
    state = GameState()
    return ClassicGameEngine(state)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def test_create_game_initializes_all_roles():
    """All four roles must be present with inventory=12 and backlog=0."""
    engine = make_engine()
    state = engine.state
    expected_roles = {Role.RETAILER, Role.WHOLESALER, Role.DISTRIBUTOR, Role.FACTORY}

    assert set(state.players.keys()) == {r.value for r in expected_roles}, (
        "Game must contain exactly retailer, wholesaler, distributor, factory"
    )
    for role_key, player in state.players.items():
        assert player.inventory == 12, f"{role_key} should start with inventory=12"
        assert player.backlog == 0, f"{role_key} should start with backlog=0"


# ---------------------------------------------------------------------------
# Customer demand
# ---------------------------------------------------------------------------

def test_customer_demand_changes_at_round_5():
    """Demand is 4 for rounds 1–4; it becomes 8 from round 5 onward."""
    engine = make_engine()

    for round_num in range(1, 5):
        demand = engine.get_customer_demand(round_num)
        assert demand == 4, f"Expected demand=4 at round {round_num}, got {demand}"

    for round_num in range(5, 10):
        demand = engine.get_customer_demand(round_num)
        assert demand == 8, f"Expected demand=8 at round {round_num}, got {demand}"


# ---------------------------------------------------------------------------
# Inventory / backlog mechanics
# ---------------------------------------------------------------------------

def test_advance_round_reduces_inventory():
    """
    When the retailer fulfils an order that is smaller than current inventory,
    inventory must decrease by the order quantity.
    Pipeline is zeroed so the only change is demand fulfilment.
    """
    engine = make_engine()
    retailer = engine.state.players[Role.RETAILER.value]
    retailer.inventory = 20
    retailer.shipping_pipeline = [0, 0]  # no in-transit goods

    orders = {role: 4 for role in engine.state.players}
    engine.advance_round(orders)

    retailer_after = engine.state.players[Role.RETAILER.value]
    # Receives 0 from pipeline, ships 4 to customer → inventory = 16
    assert retailer_after.inventory < 20, (
        "Inventory should decrease after fulfilling demand"
    )


def test_advance_round_creates_backlog():
    """
    When demand exceeds inventory, the shortfall must appear as backlog.
    Pipeline zeroed so no surprise arrivals inflate inventory.
    """
    engine = make_engine()
    retailer = engine.state.players[Role.RETAILER.value]
    retailer.inventory = 2
    retailer.shipping_pipeline = [0, 0]  # no in-transit goods

    # Demand is 4 in round 1; only 2 units available → backlog = 2
    orders = {role: 4 for role in engine.state.players}
    engine.advance_round(orders)

    retailer_after = engine.state.players[Role.RETAILER.value]
    assert retailer_after.backlog > 0, (
        "Backlog should be > 0 when demand exceeds inventory"
    )
    assert retailer_after.inventory == 0, (
        "Inventory should be 0 when fully exhausted"
    )


# ---------------------------------------------------------------------------
# Cost calculation
# ---------------------------------------------------------------------------

def test_cost_calculation():
    """
    Holding cost = $0.50/unit in inventory.
    Backlog cost = $1.00/unit in backlog.
    """
    engine = make_engine()
    retailer = engine.state.players[Role.RETAILER.value]
    retailer.inventory = 10
    retailer.backlog = 0

    cost = engine.calculate_cost(retailer)
    assert cost == pytest.approx(5.00), (
        f"Expected $5.00 holding cost for 10 units, got {cost}"
    )

    retailer.inventory = 0
    retailer.backlog = 3
    cost = engine.calculate_cost(retailer)
    assert cost == pytest.approx(3.00), (
        f"Expected $3.00 backlog cost for 3 units, got {cost}"
    )

    retailer.inventory = 4
    retailer.backlog = 2
    cost = engine.calculate_cost(retailer)
    assert cost == pytest.approx(4.00), (
        f"Expected $4.00 (2 holding + 2 backlog) for inventory=4, backlog=2, got {cost}"
    )


# ---------------------------------------------------------------------------
# AI ordering
# ---------------------------------------------------------------------------

def test_ai_order_calculation():
    """
    AI orders must be non-negative and within a reasonable upper bound
    (sanity: no more than 4× the standard demand of 8).
    """
    engine = make_engine()

    for role_key, player in engine.state.players.items():
        if not player.is_human:
            order = engine.calculate_ai_order(player)
            assert order >= 0, f"AI order for {role_key} must be non-negative"
            assert order <= 32, (
                f"AI order for {role_key} seems unreasonably large: {order}"
            )


# ---------------------------------------------------------------------------
# Game completion
# ---------------------------------------------------------------------------

def test_game_completes_after_max_rounds():
    """
    After advancing through max_rounds the game status must become 'complete'.
    """
    engine = make_engine()
    engine.state.max_rounds = 3  # shorten for speed

    for _ in range(engine.state.max_rounds):
        orders = {role: 4 for role in engine.state.players}
        engine.advance_round(orders)

    assert engine.state.status == "complete", (
        f"Expected status='complete' after {engine.state.max_rounds} rounds, "
        f"got '{engine.state.status}'"
    )


# ---------------------------------------------------------------------------
# 2-round shipping pipeline (Sterman authenticity)
# ---------------------------------------------------------------------------

def test_pipeline_delivers_with_2_round_delay():
    """
    Goods placed in pipeline[1] must arrive 2 rounds later, not 1.
    After seeding pipeline=[0,8]: round 1 receives 0, round 2 receives 8.
    """
    from core.engine.game_loop import create_game, advance_round

    state = create_game([])
    retailer = state.players[Role.RETAILER.value]
    # Zero out pipeline then set slot 1 = 8 (arrives in 2 rounds)
    for p in state.players.values():
        p.shipping_pipeline = [0, 0]
    retailer.shipping_pipeline = [0, 8]

    # Round 1: slot 0 = 0, so nothing arrives this round
    state = advance_round(state, {})
    retailer_r1 = state.players[Role.RETAILER.value]
    assert retailer_r1.incoming_shipment == 0, (
        "pipeline[0]=0 should mean nothing arrives in round 1"
    )

    # Round 2: slot 1 (=8) has advanced to slot 0, so 8 arrives
    state = advance_round(state, {})
    retailer_r2 = state.players[Role.RETAILER.value]
    assert retailer_r2.incoming_shipment == 8, (
        f"pipeline[1]=8 should arrive in round 2, got {retailer_r2.incoming_shipment}"
    )


def test_initial_steady_state():
    """
    With standard starting conditions and constant demand=4,
    round 1 should deliver 4 units to every player (pipeline[0]=4).
    """
    from core.engine.game_loop import create_game, advance_round

    state = create_game([])
    state = advance_round(state, {})

    for role, player in state.players.items():
        assert player.incoming_shipment == 4, (
            f"{role} should receive 4 units in round 1 (pipeline[0]=4), got {player.incoming_shipment}"
        )
