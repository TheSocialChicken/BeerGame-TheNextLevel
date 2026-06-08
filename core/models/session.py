import time
import uuid
import random
import string
from pydantic import BaseModel, Field

PRICE_PER_UNIT_SOLD = 5.00            # revenue when retailer fills customer order
HOLDING_COST_PER_UNIT_PER_MIN = 0.10  # $ per unit per minute in inventory
BACKLOG_COST_PER_UNIT_PER_MIN = 0.50  # $ penalty per unfilled unit per minute


class Company(BaseModel):
    company_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    player_id: str
    player_name: str
    role: str          # "factory" | "wholesaler" | "distributor" | "retailer"
    city_id: str       # where this company is located
    cash: float = 10000.0
    inventory: int = 50
    backlog: int = 0
    total_revenue: float = 0.0
    total_costs: float = 0.0
    is_bankrupt: bool = False

    @property
    def profit(self) -> float:
        return self.total_revenue - self.total_costs


class Shipment(BaseModel):
    shipment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    from_company_id: str
    to_company_id: str
    from_city: str
    to_city: str
    quantity: int
    transport_mode: str
    status: str = "in_transit"  # in_transit | delivered | failed
    departs_at: float = Field(default_factory=time.time)
    arrives_at: float = 0.0
    shipping_cost: float = 0.0


class GameSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    room_code: str = ""
    status: str = "lobby"  # lobby | active | complete
    duration_minutes: int = 30
    started_at: float = 0.0
    ends_at: float = 0.0
    companies: dict[str, Company] = {}   # company_id -> Company
    shipments: dict[str, Shipment] = {}  # shipment_id -> Shipment
    last_demand_tick: float = 0.0
    demand_interval_seconds: float = 120.0  # customer demand every 2 minutes
    customer_demand_per_tick: int = 10      # units demanded per retailer per tick


def generate_room_code() -> str:
    """Generate a random 6-letter uppercase room code."""
    return "".join(random.choices(string.ascii_uppercase, k=6))
