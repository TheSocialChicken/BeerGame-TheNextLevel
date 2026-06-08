"""
Realtime multiplayer game engine — Logistics Wars.

Pure functions, no I/O. All state is passed in and returned.

Game flow:
  - Sessions start in lobby; players join and pick a company role + city.
  - Host starts the session; timer begins.
  - Players place orders (shipments) in real time; shipments travel on a map.
  - Every demand_interval_seconds, customer demand hits all retailers.
  - Every 30s server tick: holding/backlog costs applied, session-end checked.
  - Session ends when time runs out or all companies go bankrupt.
"""

import time
from core.models.session import (
    GameSession,
    Company,
    Shipment,
    generate_room_code,
    PRICE_PER_UNIT_SOLD,
    HOLDING_COST_PER_UNIT_PER_MIN,
    BACKLOG_COST_PER_UNIT_PER_MIN,
)
from core.models.geography import EU_CITIES, get_route_mode, TransportMode


def create_session(duration_minutes: int = 30) -> GameSession:
    """Create a new session in lobby state with a random room code."""
    session = GameSession()
    session.room_code = generate_room_code()
    session.duration_minutes = duration_minutes
    return session


def add_company(
    session: GameSession,
    player_id: str,
    player_name: str,
    role: str,
    city_id: str,
) -> tuple[GameSession, Company]:
    """
    Add a player company to a lobby session.

    Raises ValueError if:
    - Session is not in lobby status.
    - city_id is not a known EU city.
    - role is not available in that city.
    """
    if session.status != "lobby":
        raise ValueError("Session not in lobby")
    city = EU_CITIES.get(city_id)
    if not city:
        raise ValueError(f"Unknown city: {city_id}")
    if role not in city.available_roles:
        raise ValueError(f"Role '{role}' not available in {city_id}")
    company = Company(
        player_id=player_id,
        player_name=player_name,
        role=role,
        city_id=city_id,
    )
    session.companies[company.company_id] = company
    return session, company


_AI_COMPANIES = [
    ("factory",     "eindhoven", "EindhAI Manufacturing"),
    ("distributor", "rotterdam", "Rotterdam Distribution BV"),
    ("wholesaler",  "amsterdam", "Amsterdam Wholesale Co"),
    ("retailer",    "berlin",    "Berlin Retail GmbH"),
]


def start_session(session: GameSession) -> GameSession:
    """
    Transition session from lobby to active and set the end timer.
    Auto-fills missing roles with AI companies so solo players have suppliers.

    Raises ValueError if session is not in lobby status.
    """
    if session.status != "lobby":
        raise ValueError("Session is not in lobby")

    # Fill missing roles with AI companies (500 units, no cash drain)
    human_roles = {c.role for c in session.companies.values()}
    for role, city_id, name in _AI_COMPANIES:
        if role not in human_roles:
            ai = Company(
                player_id=f"ai-{role}",
                player_name=name,
                role=role,
                city_id=city_id,
                inventory=500,
                cash=999_999.0,
            )
            session.companies[ai.company_id] = ai

    now = time.time()
    session.status = "active"
    session.started_at = now
    session.ends_at = now + session.duration_minutes * 60
    session.last_demand_tick = now
    return session


def place_order(
    session: GameSession,
    buyer_company_id: str,
    seller_company_id: str,
    quantity: int,
    mode: str,
) -> tuple[GameSession, Shipment]:
    """
    Buyer places an order with seller. Creates a shipment if seller has stock.

    Deducts from seller inventory and buyer cash immediately.
    Shipment is created with an arrival timestamp based on route transit time.

    Raises ValueError for invalid state, unknown companies, bankrupt parties,
    insufficient inventory, missing route, quantity below minimum, or
    insufficient buyer cash.
    """
    if session.status != "active":
        raise ValueError("Session not active")

    buyer = session.companies.get(buyer_company_id)
    seller = session.companies.get(seller_company_id)
    if not buyer or not seller:
        raise ValueError("Invalid company")
    if seller.is_bankrupt or buyer.is_bankrupt:
        raise ValueError("Bankrupt company cannot trade")
    if seller.inventory < quantity:
        raise ValueError(f"Seller only has {seller.inventory} units")

    transport = TransportMode(mode)
    route_mode = get_route_mode(seller.city_id, buyer.city_id, transport)
    if not route_mode:
        raise ValueError(f"No {mode} route from {seller.city_id} to {buyer.city_id}")
    if quantity < route_mode.min_quantity:
        raise ValueError(f"Minimum shipment for {mode}: {route_mode.min_quantity} units")

    shipping_cost = quantity * route_mode.cost_per_unit
    if buyer.cash < shipping_cost:
        raise ValueError("Buyer cannot afford shipping cost")

    # Deduct from seller inventory and buyer cash immediately
    seller.inventory -= quantity
    buyer.cash -= shipping_cost
    buyer.total_costs += shipping_cost

    now = time.time()
    arrives_at = now + route_mode.transit_minutes * 60

    shipment = Shipment(
        session_id=session.session_id,
        from_company_id=seller_company_id,
        to_company_id=buyer_company_id,
        from_city=seller.city_id,
        to_city=buyer.city_id,
        quantity=quantity,
        transport_mode=mode,
        departs_at=now,
        arrives_at=arrives_at,
        shipping_cost=shipping_cost,
    )
    session.shipments[shipment.shipment_id] = shipment
    return session, shipment


def deliver_shipment(session: GameSession, shipment_id: str) -> GameSession:
    """
    Called when a shipment timer fires. Credits inventory to the buyer.

    Also fills any existing backlog for the buyer, generating revenue
    if the buyer is a retailer.
    """
    shipment = session.shipments.get(shipment_id)
    if not shipment or shipment.status != "in_transit":
        return session

    buyer = session.companies.get(shipment.to_company_id)
    if not buyer:
        return session

    buyer.inventory += shipment.quantity

    # Fill backlog immediately on delivery
    if buyer.backlog > 0:
        filled = min(buyer.backlog, buyer.inventory)
        buyer.backlog -= filled
        buyer.inventory -= filled
        if buyer.role == "retailer":
            revenue = filled * PRICE_PER_UNIT_SOLD
            buyer.cash += revenue
            buyer.total_revenue += revenue

    shipment.status = "delivered"
    return session


def tick_costs(session: GameSession, elapsed_seconds: float) -> GameSession:
    """
    Apply holding and backlog costs for elapsed time.

    Called periodically (every 30s by the background task). Marks companies
    bankrupt when cash reaches zero.
    """
    elapsed_minutes = elapsed_seconds / 60.0
    for company in session.companies.values():
        if company.is_bankrupt:
            continue
        holding = company.inventory * HOLDING_COST_PER_UNIT_PER_MIN * elapsed_minutes
        backlog_cost = company.backlog * BACKLOG_COST_PER_UNIT_PER_MIN * elapsed_minutes
        cost = holding + backlog_cost
        company.cash -= cost
        company.total_costs += cost
        if company.cash <= 0:
            company.is_bankrupt = True
            company.cash = 0.0
    return session


def tick_customer_demand(session: GameSession) -> GameSession:
    """
    Fire customer demand at all retailer companies.

    Only executes if demand_interval_seconds have elapsed since the last tick.
    Unfilled demand goes to backlog. Filled demand generates revenue.
    """
    now = time.time()
    if now - session.last_demand_tick < session.demand_interval_seconds:
        return session
    session.last_demand_tick = now

    # AI factories replenish stock every demand tick so they never run dry
    for company in session.companies.values():
        if company.player_id.startswith("ai-") and company.role == "factory":
            company.inventory = max(company.inventory, 500)

    for company in session.companies.values():
        if company.role != "retailer" or company.is_bankrupt:
            continue
        demand = session.customer_demand_per_tick
        filled = min(company.inventory, demand)
        unfilled = demand - filled
        company.inventory -= filled
        company.backlog += unfilled
        if filled > 0:
            revenue = filled * PRICE_PER_UNIT_SOLD
            company.cash += revenue
            company.total_revenue += revenue
    return session


def check_session_end(session: GameSession) -> GameSession:
    """
    Mark session complete if time is up or all companies are bankrupt.

    Returns session unchanged if it is not active.
    """
    if session.status != "active":
        return session
    now = time.time()
    if now >= session.ends_at:
        session.status = "complete"
        return session
    if session.companies:
        all_bankrupt = all(c.is_bankrupt for c in session.companies.values())
        if all_bankrupt:
            session.status = "complete"
    return session


def get_leaderboard(session: GameSession) -> list[dict]:
    """Return companies ranked by profit (descending)."""
    return sorted(
        [
            {
                "company_id": c.company_id,
                "player_name": c.player_name,
                "role": c.role,
                "city": c.city_id,
                "cash": round(c.cash, 2),
                "profit": round(c.profit, 2),
                "is_bankrupt": c.is_bankrupt,
            }
            for c in session.companies.values()
        ],
        key=lambda x: x["profit"],
        reverse=True,
    )
