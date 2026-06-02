from enum import StrEnum


class PlayerRole(StrEnum):
    RETAILER = "retailer"
    WHOLESALER = "wholesaler"
    DISTRIBUTOR = "distributor"
    FACTORY = "factory"


ROLE_ORDER: list[PlayerRole] = [
    PlayerRole.RETAILER,
    PlayerRole.WHOLESALER,
    PlayerRole.DISTRIBUTOR,
    PlayerRole.FACTORY,
]
