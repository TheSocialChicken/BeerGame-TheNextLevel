from enum import StrEnum

from pydantic import BaseModel, Field

from .order import IncomingShipment
from .player import PlayerRole

HOLDING_COST_PER_UNIT = 0.5  # per round
BACKLOG_COST_PER_UNIT = 1.0  # per round
SHIPPING_DELAY = 2  # rounds in transit
ORDER_DELAY = 2  # rounds for order to reach supplier


class GamePhase(StrEnum):
    WAITING = "waiting"
    ACTIVE = "active"
    FINISHED = "finished"


class GameConfig(BaseModel):
    num_rounds: int = Field(default=26, ge=1, le=100)
    initial_inventory: int = Field(default=12, ge=0)
    initial_backlog: int = Field(default=0, ge=0)
    demand_pattern: list[int] = Field(default_factory=lambda: [4] * 4 + [8] * 22)
    holding_cost: float = Field(default=HOLDING_COST_PER_UNIT, ge=0)
    backlog_cost: float = Field(default=BACKLOG_COST_PER_UNIT, ge=0)
    shipping_delay: int = Field(default=SHIPPING_DELAY, ge=1)
    order_delay: int = Field(default=ORDER_DELAY, ge=1)


class PlayerState(BaseModel):
    role: PlayerRole
    inventory: int = Field(ge=0)
    backlog: int = Field(ge=0)
    incoming_shipments: list[IncomingShipment] = Field(default_factory=list)
    incoming_orders: list[int] = Field(default_factory=list)
    last_order: int = 0
    cumulative_cost: float = 0.0
    is_ai: bool = False

    def round_cost(self) -> float:
        return self.inventory * HOLDING_COST_PER_UNIT + self.backlog * BACKLOG_COST_PER_UNIT


class GameState(BaseModel):
    game_id: str
    variant: str = "classic"
    phase: GamePhase = GamePhase.WAITING
    current_round: int = 0
    config: GameConfig = Field(default_factory=GameConfig)
    players: dict[PlayerRole, PlayerState] = Field(default_factory=dict)
    customer_demand_history: list[int] = Field(default_factory=list)
    orders_this_round: dict[PlayerRole, int] = Field(default_factory=dict)

    def is_round_complete(self) -> bool:
        active_roles = {role for role, ps in self.players.items() if not ps.is_ai}
        return active_roles.issubset(self.orders_this_round.keys())

    def total_cost(self) -> float:
        return sum(ps.cumulative_cost for ps in self.players.values())
