from pydantic import BaseModel, Field

from .player import PlayerRole


class Order(BaseModel):
    quantity: int = Field(ge=0)
    from_role: PlayerRole
    to_role: PlayerRole | None = None  # None = factory produces
    delivery_round: int = Field(ge=0)


class IncomingShipment(BaseModel):
    quantity: int = Field(ge=0)
    arrives_in_rounds: int = Field(ge=0)
