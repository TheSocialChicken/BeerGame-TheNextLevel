"""
Unit tests for order_processor.py — the four core game-loop functions.
These run in isolation with hand-crafted GameState fixtures.
"""
import pytest
from core.engine.order_processor import (
    accrue_costs,
    advance_shipments,
    fulfill_orders,
    place_orders,
)
from core.models import (
    GameConfig,
    GamePhase,
    GameState,
    IncomingShipment,
    PlayerRole,
    PlayerState,
)

ROLES = [
    PlayerRole.RETAILER,
    PlayerRole.WHOLESALER,
    PlayerRole.DISTRIBUTOR,
    PlayerRole.FACTORY,
]


def make_state(
    inventory: int = 12,
    backlog: int = 0,
    shipping_delay: int = 2,
    order_delay: int = 2,
    orders: dict | None = None,
) -> GameState:
    cfg = GameConfig(
        num_rounds=4,
        initial_inventory=inventory,
        initial_backlog=backlog,
        demand_pattern=[4, 4, 4, 4],
        shipping_delay=shipping_delay,
        order_delay=order_delay,
    )
    players = {
        role: PlayerState(role=role, inventory=inventory, backlog=backlog)
        for role in ROLES
    }
    return GameState(
        game_id="test",
        phase=GamePhase.ACTIVE,
        config=cfg,
        players=players,
        orders_this_round=orders or {},
    )


# ── advance_shipments ────────────────────────────────────────────────────────

class TestAdvanceShipments:
    def test_delivers_shipment_arriving_this_round(self):
        state = make_state(inventory=0)
        state.players[PlayerRole.RETAILER].incoming_shipments = [
            IncomingShipment(quantity=5, arrives_in_rounds=1)
        ]
        state = advance_shipments(state)
        assert state.players[PlayerRole.RETAILER].inventory == 5
        assert state.players[PlayerRole.RETAILER].incoming_shipments == []

    def test_decrements_future_shipments(self):
        state = make_state(inventory=0)
        state.players[PlayerRole.RETAILER].incoming_shipments = [
            IncomingShipment(quantity=5, arrives_in_rounds=3)
        ]
        state = advance_shipments(state)
        assert state.players[PlayerRole.RETAILER].inventory == 0
        remaining = state.players[PlayerRole.RETAILER].incoming_shipments
        assert len(remaining) == 1
        assert remaining[0].arrives_in_rounds == 2

    def test_multiple_shipments_same_round(self):
        state = make_state(inventory=0)
        state.players[PlayerRole.RETAILER].incoming_shipments = [
            IncomingShipment(quantity=3, arrives_in_rounds=1),
            IncomingShipment(quantity=7, arrives_in_rounds=1),
        ]
        state = advance_shipments(state)
        assert state.players[PlayerRole.RETAILER].inventory == 10
        assert state.players[PlayerRole.RETAILER].incoming_shipments == []

    def test_mixed_arriving_and_future(self):
        state = make_state(inventory=0)
        state.players[PlayerRole.RETAILER].incoming_shipments = [
            IncomingShipment(quantity=4, arrives_in_rounds=1),
            IncomingShipment(quantity=6, arrives_in_rounds=2),
        ]
        state = advance_shipments(state)
        assert state.players[PlayerRole.RETAILER].inventory == 4
        remaining = state.players[PlayerRole.RETAILER].incoming_shipments
        assert len(remaining) == 1
        assert remaining[0].quantity == 6
        assert remaining[0].arrives_in_rounds == 1

    def test_no_shipments_no_change(self):
        state = make_state(inventory=12)
        state = advance_shipments(state)
        assert state.players[PlayerRole.RETAILER].inventory == 12

    def test_all_roles_processed(self):
        state = make_state(inventory=0)
        for role in ROLES:
            state.players[role].incoming_shipments = [
                IncomingShipment(quantity=2, arrives_in_rounds=1)
            ]
        state = advance_shipments(state)
        for role in ROLES:
            assert state.players[role].inventory == 2


# ── fulfill_orders ───────────────────────────────────────────────────────────

class TestFulfillOrders:
    def test_retailer_fills_customer_demand_fully(self):
        state = make_state(inventory=12)
        state = fulfill_orders(state, customer_demand=4)
        assert state.players[PlayerRole.RETAILER].backlog == 0
        assert state.players[PlayerRole.RETAILER].inventory == 8

    def test_partial_fill_creates_backlog(self):
        state = make_state(inventory=2)
        state = fulfill_orders(state, customer_demand=6)
        retailer = state.players[PlayerRole.RETAILER]
        assert retailer.inventory == 0
        assert retailer.backlog == 4

    def test_backlog_carries_over_and_fills_first(self):
        state = make_state(inventory=20)
        state.players[PlayerRole.RETAILER].backlog = 5
        state = fulfill_orders(state, customer_demand=4)
        retailer = state.players[PlayerRole.RETAILER]
        # demand = 4 + 5 backlog = 9 total; inventory 20 → ships 9
        assert retailer.backlog == 0
        assert retailer.inventory == 11

    def test_zero_demand_no_shipment(self):
        state = make_state(inventory=12)
        state = fulfill_orders(state, customer_demand=0)
        retailer = state.players[PlayerRole.RETAILER]
        assert retailer.inventory == 12
        assert retailer.backlog == 0

    def test_upstream_receives_shipment_in_pipeline(self):
        """Wholesaler ships to retailer; shipment lands in retailer's incoming_shipments."""
        state = make_state(inventory=12, shipping_delay=2)
        state.orders_this_round = {PlayerRole.RETAILER: 4}
        state = fulfill_orders(state, customer_demand=0)
        retailer = state.players[PlayerRole.RETAILER]
        assert any(s.quantity > 0 for s in retailer.incoming_shipments)

    def test_insufficient_inventory_propagates_backlog(self):
        """Wholesaler with 0 inventory can't fill retailer's order."""
        state = make_state(inventory=0)
        state.orders_this_round = {PlayerRole.RETAILER: 8}
        state = fulfill_orders(state, customer_demand=0)
        wholesaler = state.players[PlayerRole.WHOLESALER]
        assert wholesaler.backlog == 8

    def test_large_demand_exceeds_all_inventory(self):
        state = make_state(inventory=2)
        state = fulfill_orders(state, customer_demand=100)
        retailer = state.players[PlayerRole.RETAILER]
        assert retailer.inventory == 0
        assert retailer.backlog == 98


# ── place_orders ─────────────────────────────────────────────────────────────

class TestPlaceOrders:
    def test_retailer_order_reaches_wholesaler(self):
        state = make_state()
        state.orders_this_round = {PlayerRole.RETAILER: 5}
        state = place_orders(state)
        wholesaler = state.players[PlayerRole.WHOLESALER]
        assert 5 in wholesaler.incoming_orders

    def test_wholesaler_order_reaches_distributor(self):
        state = make_state()
        state.orders_this_round = {PlayerRole.WHOLESALER: 3}
        state = place_orders(state)
        distributor = state.players[PlayerRole.DISTRIBUTOR]
        assert 3 in distributor.incoming_orders

    def test_factory_order_schedules_production(self):
        """Factory order adds to its own shipment pipeline, not upstream."""
        state = make_state(order_delay=2)
        state.orders_this_round = {PlayerRole.FACTORY: 7}
        state = place_orders(state)
        factory = state.players[PlayerRole.FACTORY]
        production = [s for s in factory.incoming_shipments if s.quantity == 7]
        assert len(production) == 1
        assert production[0].arrives_in_rounds == 2  # order_delay

    def test_last_order_updated_for_each_role(self):
        state = make_state()
        state.orders_this_round = {role: 3 for role in ROLES}
        state = place_orders(state)
        for role in ROLES:
            assert state.players[role].last_order == 3

    def test_zero_order_still_propagates(self):
        state = make_state()
        state.orders_this_round = {PlayerRole.RETAILER: 0}
        state = place_orders(state)
        assert 0 in state.players[PlayerRole.WHOLESALER].incoming_orders


# ── accrue_costs ─────────────────────────────────────────────────────────────

class TestAccrueCosts:
    def test_holding_cost_applied(self):
        state = make_state(inventory=10, backlog=0)
        # holding_cost = 0.5 default → 10 * 0.5 = 5.0
        state = accrue_costs(state)
        for ps in state.players.values():
            assert ps.cumulative_cost == 5.0

    def test_backlog_cost_applied(self):
        state = make_state(inventory=0, backlog=4)
        # backlog_cost = 1.0 default → 4 * 1.0 = 4.0
        state = accrue_costs(state)
        for ps in state.players.values():
            assert ps.cumulative_cost == 4.0

    def test_both_costs_combined(self):
        state = make_state(inventory=10, backlog=2)
        # 10 * 0.5 + 2 * 1.0 = 7.0
        state = accrue_costs(state)
        for ps in state.players.values():
            assert ps.cumulative_cost == 7.0

    def test_custom_cost_rates(self):
        cfg = GameConfig(
            num_rounds=4, demand_pattern=[4, 4, 4, 4],
            holding_cost=1.0, backlog_cost=2.0,
        )
        state = GameState(
            game_id="test",
            config=cfg,
            players={
                role: PlayerState(role=role, inventory=4, backlog=1)
                for role in ROLES
            },
        )
        state = accrue_costs(state)
        # 4 * 1.0 + 1 * 2.0 = 6.0
        for ps in state.players.values():
            assert ps.cumulative_cost == 6.0

    def test_costs_accumulate_across_calls(self):
        state = make_state(inventory=10, backlog=0)
        state = accrue_costs(state)
        state = accrue_costs(state)
        for ps in state.players.values():
            assert ps.cumulative_cost == 10.0  # 5.0 + 5.0

    def test_zero_inventory_zero_backlog_no_cost(self):
        state = make_state(inventory=0, backlog=0)
        state = accrue_costs(state)
        for ps in state.players.values():
            assert ps.cumulative_cost == 0.0
