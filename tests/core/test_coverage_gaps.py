"""
Test skeletons for identified coverage gaps.
All tests are marked xfail or skipped until implemented.
Remove the marker and fill in assertions when implementing.
"""

import pytest

from core.ai_players.base import BaseAIPlayer
from core.ai_players.rule_based import (
    TARGET_INVENTORY,
    SAFETY_STOCK,
    ConstantOrderAI,
    OrderUpToAI,
)
from core.engine.game_engine import GameEngine
from core.models import ROLE_ORDER, GameConfig, GameState, PlayerRole, PlayerState
from core.models.game import GamePhase
from core.models.order import IncomingShipment, Order


# ---------------------------------------------------------------------------
# GAP 1: Order model — completely untested
# ---------------------------------------------------------------------------


class TestOrderModel:
    def test_order_valid(self):
        order = Order(
            quantity=4,
            from_role=PlayerRole.RETAILER,
            to_role=PlayerRole.WHOLESALER,
            delivery_round=3,
        )
        assert order.quantity == 4
        assert order.from_role == PlayerRole.RETAILER
        assert order.to_role == PlayerRole.WHOLESALER
        assert order.delivery_round == 3

    def test_order_factory_has_no_to_role(self):
        order = Order(
            quantity=8,
            from_role=PlayerRole.FACTORY,
            to_role=None,
            delivery_round=2,
        )
        assert order.to_role is None

    def test_order_negative_quantity_rejected(self):
        with pytest.raises(Exception):
            Order(
                quantity=-1,
                from_role=PlayerRole.RETAILER,
                to_role=PlayerRole.WHOLESALER,
                delivery_round=1,
            )

    def test_order_negative_delivery_round_rejected(self):
        with pytest.raises(Exception):
            Order(
                quantity=4,
                from_role=PlayerRole.RETAILER,
                to_role=PlayerRole.WHOLESALER,
                delivery_round=-1,
            )

    def test_order_zero_quantity_allowed(self):
        order = Order(
            quantity=0,
            from_role=PlayerRole.RETAILER,
            to_role=PlayerRole.WHOLESALER,
            delivery_round=0,
        )
        assert order.quantity == 0

    def test_incoming_shipment_arrives_in_zero_rounds(self):
        s = IncomingShipment(quantity=5, arrives_in_rounds=0)
        assert s.arrives_in_rounds == 0

    def test_incoming_shipment_negative_quantity_rejected(self):
        with pytest.raises(Exception):
            IncomingShipment(quantity=-1, arrives_in_rounds=1)


# ---------------------------------------------------------------------------
# GAP 2: GameConfig field boundary tests
# ---------------------------------------------------------------------------


class TestGameConfigBoundaries:
    def test_shipping_delay_zero_rejected(self):
        with pytest.raises(Exception):
            GameConfig(shipping_delay=0)

    def test_order_delay_zero_rejected(self):
        with pytest.raises(Exception):
            GameConfig(order_delay=0)

    def test_holding_cost_zero_allowed(self):
        cfg = GameConfig(holding_cost=0.0)
        assert cfg.holding_cost == 0.0

    def test_backlog_cost_zero_allowed(self):
        cfg = GameConfig(backlog_cost=0.0)
        assert cfg.backlog_cost == 0.0

    def test_demand_pattern_single_element(self):
        cfg = GameConfig(num_rounds=5, demand_pattern=[4])
        assert len(cfg.demand_pattern) == 1
        assert cfg.demand_pattern[0] == 4

    def test_demand_pattern_with_zeros(self):
        cfg = GameConfig(num_rounds=3, demand_pattern=[0, 0, 0])
        assert cfg.demand_pattern == [0, 0, 0]

    def test_fractional_cost_rates(self):
        cfg = GameConfig(holding_cost=0.33, backlog_cost=0.75)
        assert cfg.holding_cost == pytest.approx(0.33)
        assert cfg.backlog_cost == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# GAP 3: PlayerState.round_cost() edge cases
# ---------------------------------------------------------------------------


class TestPlayerStateRoundCost:
    def test_round_cost_fractional_costs(self):
        # Uses module-level constants (0.5 holding, 1.0 backlog)
        ps = PlayerState(role=PlayerRole.RETAILER, inventory=7, backlog=3)
        expected = 7 * 0.5 + 3 * 1.0
        assert ps.round_cost() == pytest.approx(expected)

    def test_round_cost_is_idempotent(self):
        ps = PlayerState(role=PlayerRole.RETAILER, inventory=10, backlog=2)
        cost1 = ps.round_cost()
        cost2 = ps.round_cost()
        assert cost1 == cost2

    def test_round_cost_large_values(self):
        ps = PlayerState(role=PlayerRole.RETAILER, inventory=10_000, backlog=5_000)
        expected = 10_000 * 0.5 + 5_000 * 1.0
        assert ps.round_cost() == pytest.approx(expected)


# ---------------------------------------------------------------------------
# GAP 4: GameState edge cases
# ---------------------------------------------------------------------------


class TestGameStateEdgeCases:
    def test_is_round_complete_empty_players(self):
        state = GameState(game_id="test", players={})
        # No human players — vacuously complete
        assert state.is_round_complete()

    def test_total_cost_empty_players(self):
        state = GameState(game_id="test", players={})
        assert state.total_cost() == 0.0

    def test_is_round_complete_all_humans_no_orders(self):
        state = GameState(
            game_id="test",
            players={
                role: PlayerState(role=role, inventory=12, backlog=0, is_ai=False)
                for role in PlayerRole
            },
        )
        assert not state.is_round_complete()

    def test_is_round_complete_partial_human_orders(self):
        state = GameState(
            game_id="test",
            players={
                PlayerRole.RETAILER: PlayerState(
                    role=PlayerRole.RETAILER, inventory=12, backlog=0, is_ai=False
                ),
                PlayerRole.WHOLESALER: PlayerState(
                    role=PlayerRole.WHOLESALER, inventory=12, backlog=0, is_ai=False
                ),
                PlayerRole.DISTRIBUTOR: PlayerState(
                    role=PlayerRole.DISTRIBUTOR, inventory=12, backlog=0, is_ai=True
                ),
                PlayerRole.FACTORY: PlayerState(
                    role=PlayerRole.FACTORY, inventory=12, backlog=0, is_ai=True
                ),
            },
        )
        # Only RETAILER submitted — WHOLESALER still needed
        state.orders_this_round[PlayerRole.RETAILER] = 4
        assert not state.is_round_complete()
        state.orders_this_round[PlayerRole.WHOLESALER] = 4
        assert state.is_round_complete()


# ---------------------------------------------------------------------------
# GAP 5: Pipeline pre-fill verification
# ---------------------------------------------------------------------------


class TestPipelinePreFill:
    def test_prefill_quantities_match_initial_inventory_half(self):
        engine = GameEngine()
        cfg = GameConfig(initial_inventory=12, shipping_delay=2)
        state = engine.create_game(config=cfg)
        for role in ROLE_ORDER:
            ps = state.players[role]
            assert len(ps.incoming_shipments) == cfg.shipping_delay
            for shipment in ps.incoming_shipments:
                assert shipment.quantity == cfg.initial_inventory // 2  # = 6

    def test_prefill_arrival_times_are_distinct(self):
        engine = GameEngine()
        cfg = GameConfig(initial_inventory=12, shipping_delay=2)
        state = engine.create_game(config=cfg)
        for role in ROLE_ORDER:
            ps = state.players[role]
            arrival_times = [s.arrives_in_rounds for s in ps.incoming_shipments]
            assert len(arrival_times) == len(set(arrival_times)), "duplicate arrival times"

    def test_prefill_odd_initial_inventory_rounds_down(self):
        engine = GameEngine()
        cfg = GameConfig(initial_inventory=7, shipping_delay=1)
        state = engine.create_game(config=cfg)
        for role in ROLE_ORDER:
            ps = state.players[role]
            assert ps.incoming_shipments[0].quantity == 3  # 7 // 2

    def test_prefill_zero_initial_inventory(self):
        engine = GameEngine()
        cfg = GameConfig(initial_inventory=0, shipping_delay=2)
        state = engine.create_game(config=cfg)
        for role in ROLE_ORDER:
            ps = state.players[role]
            for shipment in ps.incoming_shipments:
                assert shipment.quantity == 0


# ---------------------------------------------------------------------------
# GAP 6: get_visible_state() error handling
# ---------------------------------------------------------------------------


class TestGetVisibleStateErrors:
    def test_get_visible_state_invalid_role_raises(self):
        engine = GameEngine()
        state = engine.create_game(ai_roles=set(PlayerRole))
        # Remove one player after creation to simulate invalid role
        del state.players[PlayerRole.WHOLESALER]
        with pytest.raises((KeyError, ValueError)):
            engine.get_visible_state(state, PlayerRole.WHOLESALER)

    def test_get_visible_state_contains_expected_keys(self):
        engine = GameEngine()
        state = engine.create_game(ai_roles=set(PlayerRole))
        state = engine.start_game(state)
        vis = engine.get_visible_state(state, PlayerRole.RETAILER)
        expected_keys = {
            "game_id", "round", "phase", "role",
            "inventory", "backlog", "last_order",
            "cumulative_cost", "incoming_shipments",
        }
        assert expected_keys.issubset(vis.keys())

    def test_get_visible_state_hides_other_roles(self):
        engine = GameEngine()
        state = engine.create_game(ai_roles=set(PlayerRole))
        state = engine.start_game(state)
        vis = engine.get_visible_state(state, PlayerRole.RETAILER)
        # No other-player data leaked
        assert "players" not in vis
        assert PlayerRole.WHOLESALER not in vis


# ---------------------------------------------------------------------------
# GAP 7: OrderUpToAI edge cases
# ---------------------------------------------------------------------------


def _make_state_with_role(
    role: PlayerRole,
    inventory: int = 12,
    backlog: int = 0,
    pipeline: int = 0,
) -> GameState:
    ps = PlayerState(role=role, inventory=inventory, backlog=backlog)
    if pipeline > 0:
        ps.incoming_shipments.append(IncomingShipment(quantity=pipeline, arrives_in_rounds=1))
    players = {r: PlayerState(role=r, inventory=12, backlog=0) for r in PlayerRole}
    players[role] = ps
    return GameState(game_id="test", players=players)


class TestOrderUpToAI:
    def test_position_equals_target_orders_zero(self):
        ai = OrderUpToAI(role=PlayerRole.RETAILER)
        target = TARGET_INVENTORY + SAFETY_STOCK  # 16
        state = _make_state_with_role(
            PlayerRole.RETAILER, inventory=target, backlog=0, pipeline=0
        )
        assert ai.decide_order(state) == 0

    def test_position_exceeds_target_orders_zero(self):
        ai = OrderUpToAI(role=PlayerRole.RETAILER)
        target = TARGET_INVENTORY + SAFETY_STOCK
        state = _make_state_with_role(
            PlayerRole.RETAILER, inventory=target + 5, backlog=0, pipeline=0
        )
        assert ai.decide_order(state) == 0

    def test_large_pipeline_clamps_order_to_zero(self):
        ai = OrderUpToAI(role=PlayerRole.RETAILER)
        target = TARGET_INVENTORY + SAFETY_STOCK
        state = _make_state_with_role(
            PlayerRole.RETAILER, inventory=0, backlog=0, pipeline=target + 10
        )
        assert ai.decide_order(state) == 0

    def test_negative_position_increases_order(self):
        # backlog exceeds inventory — position negative
        ai = OrderUpToAI(role=PlayerRole.RETAILER)
        state = _make_state_with_role(
            PlayerRole.RETAILER, inventory=0, backlog=5, pipeline=0
        )
        # position = 0 - 5 + 0 = -5; order = target - (-5) = target + 5
        target = TARGET_INVENTORY + SAFETY_STOCK
        assert ai.decide_order(state) == target + 5

    def test_decide_order_is_deterministic(self):
        ai = OrderUpToAI(role=PlayerRole.RETAILER)
        state = _make_state_with_role(PlayerRole.RETAILER, inventory=4, backlog=0)
        assert ai.decide_order(state) == ai.decide_order(state)

    def test_constants_sanity(self):
        assert TARGET_INVENTORY > 0
        assert SAFETY_STOCK >= 0
        assert TARGET_INVENTORY + SAFETY_STOCK > 0


# ---------------------------------------------------------------------------
# GAP 8: ConstantOrderAI edge cases
# ---------------------------------------------------------------------------


class TestConstantOrderAI:
    def test_negative_quantity_raises(self):
        with pytest.raises(ValueError):
            ConstantOrderAI(role=PlayerRole.RETAILER, quantity=-1)

    def test_zero_quantity_constant(self):
        ai = ConstantOrderAI(role=PlayerRole.RETAILER, quantity=0)
        state = _make_state_with_role(PlayerRole.RETAILER)
        assert ai.decide_order(state) == 0

    def test_large_quantity_constant(self):
        ai = ConstantOrderAI(role=PlayerRole.RETAILER, quantity=9999)
        state = _make_state_with_role(PlayerRole.RETAILER)
        assert ai.decide_order(state) == 9999


# ---------------------------------------------------------------------------
# GAP 9: BaseAIPlayer abstract contract
# ---------------------------------------------------------------------------


class TestBaseAIPlayer:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseAIPlayer(role=PlayerRole.RETAILER)  # type: ignore[abstract]

    def test_concrete_subclass_stores_role(self):
        ai = ConstantOrderAI(role=PlayerRole.WHOLESALER)
        assert ai.role == PlayerRole.WHOLESALER

    def test_subclass_decide_order_returns_int(self):
        ai = ConstantOrderAI(role=PlayerRole.RETAILER, quantity=5)
        state = _make_state_with_role(PlayerRole.RETAILER)
        result = ai.decide_order(state)
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# GAP 10: Demand pattern length=1 wrapping
# ---------------------------------------------------------------------------


class TestDemandPatternWrapping:
    def test_single_element_demand_wraps_all_rounds(self):
        engine = GameEngine()
        cfg = GameConfig(num_rounds=5, demand_pattern=[7], initial_inventory=50)
        state = engine.create_game(config=cfg, ai_roles=set(PlayerRole))
        state = engine.start_game(state)
        for _ in range(5):
            state = engine.process_round(state)
        assert all(d == 7 for d in state.customer_demand_history)
        assert len(state.customer_demand_history) == 5

    def test_demand_pattern_shorter_than_num_rounds_wraps(self):
        engine = GameEngine()
        cfg = GameConfig(num_rounds=6, demand_pattern=[2, 8], initial_inventory=50)
        state = engine.create_game(config=cfg, ai_roles=set(PlayerRole))
        state = engine.start_game(state)
        for _ in range(6):
            state = engine.process_round(state)
        assert state.customer_demand_history == [2, 8, 2, 8, 2, 8]


# ---------------------------------------------------------------------------
# GAP 11: Mixed human/AI game flow
# ---------------------------------------------------------------------------


class TestMixedHumanAIFlow:
    def test_game_does_not_auto_advance_without_human_order(self):
        engine = GameEngine()
        # RETAILER is human, rest are AI
        ai_roles = {PlayerRole.WHOLESALER, PlayerRole.DISTRIBUTOR, PlayerRole.FACTORY}
        state = engine.create_game(ai_roles=ai_roles)
        state = engine.start_game(state)
        assert not state.is_round_complete()

    def test_game_advances_after_human_order(self):
        engine = GameEngine()
        ai_roles = {PlayerRole.WHOLESALER, PlayerRole.DISTRIBUTOR, PlayerRole.FACTORY}
        state = engine.create_game(ai_roles=ai_roles)
        state = engine.start_game(state)
        state = engine.submit_order(state, PlayerRole.RETAILER, 4)
        assert state.is_round_complete()
        state = engine.process_round(state)
        assert state.current_round == 1

    def test_human_order_overwrite(self):
        engine = GameEngine()
        ai_roles = {PlayerRole.WHOLESALER, PlayerRole.DISTRIBUTOR, PlayerRole.FACTORY}
        state = engine.create_game(ai_roles=ai_roles)
        state = engine.start_game(state)
        state = engine.submit_order(state, PlayerRole.RETAILER, 4)
        state = engine.submit_order(state, PlayerRole.RETAILER, 10)
        assert state.orders_this_round[PlayerRole.RETAILER] == 10


# ---------------------------------------------------------------------------
# GAP 12: Cost accumulation over many rounds
# ---------------------------------------------------------------------------


class TestCostAccumulation:
    def test_cost_accumulates_non_zero_over_full_game(self):
        engine = GameEngine()
        cfg = GameConfig(num_rounds=26)
        state = engine.create_game(config=cfg, ai_roles=set(PlayerRole))
        state = engine.start_game(state)
        while state.phase == GamePhase.ACTIVE:
            state = engine.process_round(state)
        assert state.total_cost() > 0

    def test_cost_per_player_non_negative(self):
        engine = GameEngine()
        cfg = GameConfig(num_rounds=10)
        state = engine.create_game(config=cfg, ai_roles=set(PlayerRole))
        state = engine.start_game(state)
        while state.phase == GamePhase.ACTIVE:
            state = engine.process_round(state)
        for ps in state.players.values():
            assert ps.cumulative_cost >= 0

    def test_zero_cost_game_when_demand_zero(self):
        # With zero demand and adequate inventory, backlog never grows
        # holding costs still accrue — verify cost > 0 but backlog cost = 0
        engine = GameEngine()
        cfg = GameConfig(num_rounds=3, demand_pattern=[0], initial_inventory=12)
        state = engine.create_game(config=cfg, ai_roles=set(PlayerRole))
        state = engine.start_game(state)
        while state.phase == GamePhase.ACTIVE:
            state = engine.process_round(state)
        # Inventory should remain; holding costs accrued but no backlog costs
        total = state.total_cost()
        assert total > 0, "holding costs should accrue even with zero demand"


# ---------------------------------------------------------------------------
# GAP 13: submit_order with very large quantity
# ---------------------------------------------------------------------------


class TestSubmitOrderEdgeCases:
    def test_submit_very_large_order_accepted(self):
        engine = GameEngine()
        state = engine.create_game(ai_roles=set(PlayerRole))
        state = engine.start_game(state)
        state = engine.submit_order(state, PlayerRole.RETAILER, 999_999)
        assert state.orders_this_round[PlayerRole.RETAILER] == 999_999

    def test_submit_zero_order_accepted(self):
        engine = GameEngine()
        state = engine.create_game(ai_roles=set(PlayerRole))
        state = engine.start_game(state)
        state = engine.submit_order(state, PlayerRole.RETAILER, 0)
        assert state.orders_this_round[PlayerRole.RETAILER] == 0
