from core.models import GameConfig

CLASSIC_DESCRIPTION: str = "Classic Beer Game — 4-player supply chain, 26 rounds, demand step change"

CLASSIC_CONFIG = GameConfig(
    num_rounds=26,
    initial_inventory=12,
    initial_backlog=0,
    demand_pattern=[4, 4, 4, 4] + [8] * 22,
    holding_cost=0.5,
    backlog_cost=1.0,
    shipping_delay=2,
    order_delay=2,
)


def get_classic_config() -> GameConfig:
    return GameConfig(**CLASSIC_CONFIG.model_dump())
