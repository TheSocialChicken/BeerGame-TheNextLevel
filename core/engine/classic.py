from core.engine.game_loop import create_game, advance_round, get_customer_demand, _ai_order
from core.models.game import GameState, PlayerState


class ClassicGameEngine:
    def __init__(self, state_or_roles: "GameState | list[str] | None" = None):
        if isinstance(state_or_roles, GameState) and state_or_roles.players:
            self.state = state_or_roles
        elif isinstance(state_or_roles, list):
            self.state = create_game(state_or_roles)
        else:
            self.state = create_game([])

    def get_customer_demand(self, round: int) -> int:
        return get_customer_demand(round)

    def advance_round(self, orders: dict[str, int]) -> GameState:
        self.state = advance_round(self.state, orders)
        return self.state

    def calculate_cost(self, player: PlayerState) -> float:
        holding = player.inventory * 0.50
        backlog = player.backlog * 1.00
        return holding + backlog

    def calculate_ai_order(self, player: PlayerState) -> int:
        return _ai_order(player)
