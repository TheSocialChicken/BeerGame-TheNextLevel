"""
Classic Beer Game engine — MIT Sterman (1989) rules.

Turn sequence each round:
  1. Receive shipment: pipeline[0] → inventory (2-round shipping delay)
  2. Receive incoming orders from downstream (1-round order delay)
  3. Fill orders: ship = min(inventory, backlog + incoming_order)
  4. Calculate holding / backlog costs
  5. Advance pipeline: slot1→slot0; upstream's dispatch→slot1
  6. Place orders: AI anchor-and-adjust or human input

Shipping pipeline (per player, represents goods in transit TO that player):
  pipeline[0] = arrives THIS round
  pipeline[1] = arrives NEXT round
  Initial: [4, 4] — steady-state pre-seeded pipeline

Customer demand schedule (MIT classic):
  - Rounds 1-4 : 4 units
  - Round  5+  : 8 units  (step change causes bullwhip effect)

Costs:
  - Holding: $0.50 / unit / round
  - Backlog: $1.00 / unit / round
"""

from core.models.game import GameState, PlayerState, Role, ROLE_ORDER, RoundSnapshot

# ── Constants ──────────────────────────────────────────────────────────────────

HOLDING_COST: float = 0.50
BACKLOG_COST: float = 1.00
TARGET_INVENTORY: int = 12
INITIAL_INVENTORY: int = 12
DEMAND_STEP_ROUND: int = 5
DEMAND_LOW: int = 4
DEMAND_HIGH: int = 8


# ── Public API ─────────────────────────────────────────────────────────────────

def create_game(human_roles: list[str] | None = None) -> GameState:
    """
    Initialise a new game with Sterman starting conditions.

    Starting state: 12 units inventory, pipeline [4, 4] (8 units in transit),
    order_placed=4 (steady-state). All roles start balanced.
    """
    if human_roles is None:
        human_roles = []

    human_role_set = {Role(r) for r in human_roles}

    players: dict[str, PlayerState] = {}
    for role in ROLE_ORDER:
        players[role.value] = PlayerState(
            role=role,
            inventory=INITIAL_INVENTORY,
            shipping_pipeline=[4, 4],
            order_placed=4,
            is_human=(role in human_role_set),
        )

    return GameState(
        round=0,
        status="active",
        players=players,
        customer_demand=DEMAND_LOW,
    )


def get_customer_demand(round_number: int) -> int:
    """Rounds 1-4 → 4 units. Round 5+ → 8 units."""
    return DEMAND_HIGH if round_number >= DEMAND_STEP_ROUND else DEMAND_LOW


def advance_round(state: GameState, human_orders: dict[str, int]) -> GameState:
    """
    Process one complete round of the Beer Game.

    human_orders: role_name → order_quantity for human-controlled roles.
    Returns updated GameState. No-op if already complete.
    """
    if state.status == "complete":
        return state

    s = state.model_copy(deep=True)
    s.round += 1
    s.status = "active"

    demand = get_customer_demand(s.round)
    s.customer_demand = demand

    # ── Step 1: Receive shipments from pipeline slot 0 ────────────────────────
    for role in ROLE_ORDER:
        player = s.players[role.value]
        player.incoming_shipment = player.shipping_pipeline[0]
        player.inventory += player.incoming_shipment

    # ── Step 2: Receive incoming orders ───────────────────────────────────────
    # Retailer gets customer demand; others get downstream's last-round order.
    for i, role in enumerate(ROLE_ORDER):
        player = s.players[role.value]
        if i == 0:
            player.incoming_order = demand
        else:
            downstream = s.players[ROLE_ORDER[i - 1].value]
            player.incoming_order = downstream.order_placed

    # ── Step 3: Fill orders ───────────────────────────────────────────────────
    # Track how much each role ships (needed for pipeline advance in step 5).
    shipped: dict[str, int] = {}
    for role in ROLE_ORDER:
        player = s.players[role.value]
        to_ship = player.backlog + player.incoming_order
        amount = min(player.inventory, to_ship)
        player.inventory -= amount
        player.backlog = to_ship - amount
        shipped[role.value] = amount

    # ── Step 4: Calculate costs ───────────────────────────────────────────────
    for role in ROLE_ORDER:
        player = s.players[role.value]
        player.cost_this_round = player.inventory * HOLDING_COST + player.backlog * BACKLOG_COST
        player.total_cost += player.cost_this_round

    # ── Step 5: Advance pipeline + inject new dispatches ─────────────────────
    # pipeline[0] = pipeline[1]  (slot 1 becomes the arriving slot next round)
    # pipeline[1] = new dispatch from upstream
    #
    # Factory is special: its "upstream" is its own production.
    # Factory produces what it ordered last round (order_placed before step 6).
    for i, role in enumerate(ROLE_ORDER):
        player = s.players[role.value]
        player.shipping_pipeline[0] = player.shipping_pipeline[1]
        if role == Role.FACTORY:
            # Factory produces last round's order (order_placed not yet updated this round)
            player.shipping_pipeline[1] = player.order_placed
        else:
            upstream_role = ROLE_ORDER[i + 1]
            player.shipping_pipeline[1] = shipped[upstream_role.value]

    # ── Step 6: Place orders ──────────────────────────────────────────────────
    for role in ROLE_ORDER:
        player = s.players[role.value]
        if player.is_human:
            player.order_placed = human_orders.get(role.value, 0)
        else:
            player.order_placed = _ai_order(player)

    s.orders_this_round = {r.value: s.players[r.value].order_placed for r in ROLE_ORDER}

    # ── Step 7: Snapshot + completion check ───────────────────────────────────
    s.history.append(RoundSnapshot(
        round_number=s.round,
        players={k: v.model_copy() for k, v in s.players.items()},
    ))

    if s.round >= s.max_rounds:
        s.status = "complete"

    return s


# ── Internal helpers ───────────────────────────────────────────────────────────

def _ai_order(player: PlayerState) -> int:
    """Anchor-and-adjust: target TARGET_INVENTORY on hand."""
    gap = TARGET_INVENTORY - player.inventory + player.backlog
    return max(0, player.incoming_order + gap)
