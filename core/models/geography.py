from enum import Enum
from pydantic import BaseModel


class TransportMode(str, Enum):
    TRUCK = "truck"
    TRAIN = "train"
    SHIP = "ship"


class City(BaseModel):
    city_id: str
    name: str
    country: str
    lat: float
    lon: float
    available_roles: list[str]  # roles companies here can play


class RouteMode(BaseModel):
    mode: TransportMode
    transit_minutes: int   # game minutes for shipment to arrive
    cost_per_unit: float   # $ per unit shipped
    min_quantity: int = 1  # minimum shipment size


class Route(BaseModel):
    from_city: str
    to_city: str
    modes: list[RouteMode]


# Hardcoded EU geography
EU_CITIES: dict[str, City] = {
    "eindhoven": City(city_id="eindhoven", name="Eindhoven", country="NL", lat=51.4416, lon=5.4697, available_roles=["factory"]),
    "hamburg": City(city_id="hamburg", name="Hamburg", country="DE", lat=53.5488, lon=9.9872, available_roles=["factory", "distributor"]),
    "rotterdam": City(city_id="rotterdam", name="Rotterdam", country="NL", lat=51.9244, lon=4.4777, available_roles=["distributor", "wholesaler"]),
    "antwerp": City(city_id="antwerp", name="Antwerp", country="BE", lat=51.2213, lon=4.4051, available_roles=["distributor", "wholesaler"]),
    "amsterdam": City(city_id="amsterdam", name="Amsterdam", country="NL", lat=52.3676, lon=4.9041, available_roles=["wholesaler", "retailer"]),
    "cologne": City(city_id="cologne", name="Cologne", country="DE", lat=50.9333, lon=6.9500, available_roles=["wholesaler", "distributor"]),
    "brussels": City(city_id="brussels", name="Brussels", country="BE", lat=50.8503, lon=4.3517, available_roles=["wholesaler", "retailer"]),
    "berlin": City(city_id="berlin", name="Berlin", country="DE", lat=52.5200, lon=13.4050, available_roles=["retailer"]),
    "paris": City(city_id="paris", name="Paris", country="FR", lat=48.8566, lon=2.3522, available_roles=["retailer"]),
    "london": City(city_id="london", name="London", country="GB", lat=51.5074, lon=-0.1278, available_roles=["retailer"]),
}

EU_ROUTES: list[Route] = [
    Route(from_city="eindhoven", to_city="rotterdam", modes=[
        RouteMode(mode=TransportMode.TRUCK, transit_minutes=4, cost_per_unit=1.50),
        RouteMode(mode=TransportMode.TRAIN, transit_minutes=3, cost_per_unit=0.80, min_quantity=20),
    ]),
    Route(from_city="hamburg", to_city="cologne", modes=[
        RouteMode(mode=TransportMode.TRUCK, transit_minutes=5, cost_per_unit=1.50),
        RouteMode(mode=TransportMode.TRAIN, transit_minutes=4, cost_per_unit=0.80, min_quantity=20),
    ]),
    Route(from_city="hamburg", to_city="rotterdam", modes=[
        RouteMode(mode=TransportMode.TRUCK, transit_minutes=6, cost_per_unit=1.50),
        RouteMode(mode=TransportMode.SHIP, transit_minutes=12, cost_per_unit=0.40, min_quantity=50),
    ]),
    Route(from_city="rotterdam", to_city="amsterdam", modes=[
        RouteMode(mode=TransportMode.TRUCK, transit_minutes=3, cost_per_unit=1.50),
        RouteMode(mode=TransportMode.TRAIN, transit_minutes=2, cost_per_unit=0.80, min_quantity=20),
    ]),
    Route(from_city="rotterdam", to_city="antwerp", modes=[
        RouteMode(mode=TransportMode.TRUCK, transit_minutes=4, cost_per_unit=1.50),
        RouteMode(mode=TransportMode.SHIP, transit_minutes=8, cost_per_unit=0.40, min_quantity=50),
    ]),
    Route(from_city="antwerp", to_city="brussels", modes=[
        RouteMode(mode=TransportMode.TRUCK, transit_minutes=3, cost_per_unit=1.50),
        RouteMode(mode=TransportMode.TRAIN, transit_minutes=2, cost_per_unit=0.80, min_quantity=20),
    ]),
    Route(from_city="antwerp", to_city="cologne", modes=[
        RouteMode(mode=TransportMode.TRUCK, transit_minutes=4, cost_per_unit=1.50),
        RouteMode(mode=TransportMode.TRAIN, transit_minutes=3, cost_per_unit=0.80, min_quantity=20),
    ]),
    Route(from_city="cologne", to_city="berlin", modes=[
        RouteMode(mode=TransportMode.TRUCK, transit_minutes=5, cost_per_unit=1.50),
        RouteMode(mode=TransportMode.TRAIN, transit_minutes=3, cost_per_unit=0.80, min_quantity=20),
    ]),
    Route(from_city="amsterdam", to_city="brussels", modes=[
        RouteMode(mode=TransportMode.TRUCK, transit_minutes=4, cost_per_unit=1.50),
    ]),
    Route(from_city="brussels", to_city="paris", modes=[
        RouteMode(mode=TransportMode.TRUCK, transit_minutes=7, cost_per_unit=1.50),
        RouteMode(mode=TransportMode.TRAIN, transit_minutes=5, cost_per_unit=0.80, min_quantity=20),
    ]),
    Route(from_city="rotterdam", to_city="london", modes=[
        RouteMode(mode=TransportMode.SHIP, transit_minutes=15, cost_per_unit=0.40, min_quantity=50),
    ]),
    Route(from_city="hamburg", to_city="berlin", modes=[
        RouteMode(mode=TransportMode.TRUCK, transit_minutes=4, cost_per_unit=1.50),
        RouteMode(mode=TransportMode.TRAIN, transit_minutes=2, cost_per_unit=0.80, min_quantity=20),
    ]),
    # Wholesaler (Amsterdam) → Retailer cities
    Route(from_city="amsterdam", to_city="berlin", modes=[
        RouteMode(mode=TransportMode.TRUCK, transit_minutes=8, cost_per_unit=1.50),
        RouteMode(mode=TransportMode.TRAIN, transit_minutes=5, cost_per_unit=0.80, min_quantity=20),
    ]),
    Route(from_city="amsterdam", to_city="paris", modes=[
        RouteMode(mode=TransportMode.TRUCK, transit_minutes=9, cost_per_unit=1.50),
        RouteMode(mode=TransportMode.TRAIN, transit_minutes=6, cost_per_unit=0.80, min_quantity=20),
    ]),
    Route(from_city="amsterdam", to_city="london", modes=[
        RouteMode(mode=TransportMode.SHIP, transit_minutes=18, cost_per_unit=0.40, min_quantity=50),
    ]),
    Route(from_city="cologne", to_city="paris", modes=[
        RouteMode(mode=TransportMode.TRUCK, transit_minutes=8, cost_per_unit=1.50),
        RouteMode(mode=TransportMode.TRAIN, transit_minutes=5, cost_per_unit=0.80, min_quantity=20),
    ]),
    Route(from_city="brussels", to_city="london", modes=[
        RouteMode(mode=TransportMode.SHIP, transit_minutes=20, cost_per_unit=0.40, min_quantity=50),
    ]),
]


UPSTREAM_ROLE: dict[str, str | None] = {
    "retailer":    "wholesaler",
    "wholesaler":  "distributor",
    "distributor": "factory",
    "factory":     None,
}

DOWNSTREAM_ROLE: dict[str, str | None] = {
    "factory":     "distributor",
    "distributor": "wholesaler",
    "wholesaler":  "retailer",
    "retailer":    None,
}


def get_route(from_city: str, to_city: str) -> Route | None:
    """Return the route between two cities, checking both directions."""
    for r in EU_ROUTES:
        if r.from_city == from_city and r.to_city == to_city:
            return r
        if r.from_city == to_city and r.to_city == from_city:
            # Return reversed for bidirectional routes
            return Route(from_city=from_city, to_city=to_city, modes=r.modes)
    return None


def get_route_mode(from_city: str, to_city: str, mode: TransportMode) -> RouteMode | None:
    """Return the specific transport mode details for a city pair, if available."""
    route = get_route(from_city, to_city)
    if not route:
        return None
    for rm in route.modes:
        if rm.mode == mode:
            return rm
    return None
