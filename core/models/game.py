from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
import uuid


class Role(str, Enum):
    RETAILER = "retailer"
    WHOLESALER = "wholesaler"
    DISTRIBUTOR = "distributor"
    FACTORY = "factory"


# Ordered downstream → upstream (retailer is closest to customer)
ROLE_ORDER = [Role.RETAILER, Role.WHOLESALER, Role.DISTRIBUTOR, Role.FACTORY]


class PlayerState(BaseModel):
    role: Role
    inventory: int = 12
    backlog: int = 0
    shipping_pipeline: list[int] = [4, 4]  # [arrives_this_round, arrives_next_round]
    incoming_shipment: int = 0
    incoming_order: int = 0
    order_placed: int = 4  # steady-state start
    cost_this_round: float = 0.0
    total_cost: float = 0.0
    is_human: bool = False


class RoundSnapshot(BaseModel):
    round_number: int
    players: dict[str, PlayerState]


class GameState(BaseModel):
    game_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    round: int = 0
    max_rounds: int = 35
    status: str = "waiting"  # waiting | active | complete
    players: dict[str, PlayerState] = {}
    history: list[RoundSnapshot] = []
    customer_demand: int = 4
    orders_this_round: dict[str, int] = {}  # role -> order placed this round
