"""
Logistics Wars — Realtime multiplayer supply chain game.

API server for the realtime variant. Runs on port 8001.

Endpoints:
  POST   /api/sessions                          Create a new session
  POST   /api/sessions/{room_code}/join         Join by room code
  POST   /api/sessions/{session_id}/start       Host starts the game
  GET    /api/sessions/{session_id}             Get full session state
  POST   /api/sessions/{session_id}/orders      Place an order / create shipment
  GET    /api/sessions/{session_id}/leaderboard Current rankings
  GET    /api/map                               EU cities and routes
  WS     /ws/sessions/{session_id}             Realtime session state stream
"""

import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.engine.realtime import (
    add_company,
    check_session_end,
    create_session,
    deliver_shipment,
    get_leaderboard,
    place_order,
    start_session,
    tick_costs,
    tick_customer_demand,
)
from core.models.geography import EU_CITIES, EU_ROUTES, UPSTREAM_ROLE, DOWNSTREAM_ROLE
from core.models.session import GameSession

# ── In-memory stores ────────────────────────────────────────────────────────

_sessions: dict[str, GameSession] = {}        # session_id -> GameSession
_room_codes: dict[str, str] = {}              # room_code -> session_id
_ws_connections: dict[str, list[WebSocket]] = {}  # session_id -> [WebSocket]


# ── WebSocket broadcast ──────────────────────────────────────────────────────

async def _broadcast_session(session_id: str) -> None:
    """Send full session state as JSON to all connected WebSocket clients."""
    session = _sessions.get(session_id)
    if not session:
        return
    payload = session.model_dump_json()
    dead: list[WebSocket] = []
    for ws in list(_ws_connections.get(session_id, [])):
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    # Prune dead connections
    if dead:
        conns = _ws_connections.get(session_id, [])
        for ws in dead:
            if ws in conns:
                conns.remove(ws)


# ── Background tasks ────────────────────────────────────────────────────────

async def shipment_worker() -> None:
    """
    Every 5 seconds: scan all active sessions for arrived shipments.
    Deliver them and broadcast updated state to WebSocket clients.
    """
    while True:
        await asyncio.sleep(5)
        now = time.time()
        for session in list(_sessions.values()):
            if session.status != "active":
                continue
            changed = False
            for shipment in session.shipments.values():
                if shipment.status == "in_transit" and shipment.arrives_at <= now:
                    deliver_shipment(session, shipment.shipment_id)
                    changed = True
            if changed:
                await _broadcast_session(session.session_id)


async def game_tick() -> None:
    """
    Every 30 seconds: apply holding/backlog costs, tick customer demand,
    check for session end, and broadcast state to all WebSocket clients.
    """
    last_tick: dict[str, float] = {}
    while True:
        await asyncio.sleep(30)
        now = time.time()
        for session in list(_sessions.values()):
            if session.status != "active":
                continue
            elapsed = now - last_tick.get(session.session_id, session.started_at)
            tick_costs(session, elapsed)
            tick_customer_demand(session)
            check_session_end(session)
            last_tick[session.session_id] = now
            await _broadcast_session(session.session_id)


# ── App lifespan ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_task = asyncio.create_task(shipment_worker())
    tick_task = asyncio.create_task(game_tick())
    yield
    worker_task.cancel()
    tick_task.cancel()


app = FastAPI(title="Logistics Wars API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / response schemas ───────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    duration_minutes: int = 30


class JoinSessionRequest(BaseModel):
    player_name: str
    role: str
    city_id: str


class PlaceOrderRequest(BaseModel):
    buyer_company_id: str
    seller_company_id: str
    quantity: int
    transport_mode: str


# ── REST endpoints ────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/api/sessions", status_code=201)
async def create_session_endpoint(body: CreateSessionRequest) -> dict:
    """Create a new game session in lobby state."""
    session = create_session(duration_minutes=body.duration_minutes)
    _sessions[session.session_id] = session
    _room_codes[session.room_code] = session.session_id
    return {
        "session_id": session.session_id,
        "room_code": session.room_code,
        "status": session.status,
        "duration_minutes": session.duration_minutes,
    }


@app.post("/api/sessions/{room_code}/join", status_code=201)
async def join_session(room_code: str, body: JoinSessionRequest) -> dict:
    """
    Join an existing lobby session by room code.

    Assigns a unique player_id (UUID) automatically.
    Returns the new company details and its company_id.
    """
    session_id = _room_codes.get(room_code.upper())
    if not session_id:
        raise HTTPException(status_code=404, detail="Room not found")
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    import uuid
    player_id = str(uuid.uuid4())

    try:
        session, company = add_company(
            session,
            player_id=player_id,
            player_name=body.player_name,
            role=body.role,
            city_id=body.city_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await _broadcast_session(session_id)
    return {
        "company_id": company.company_id,
        "player_id": company.player_id,
        "player_name": company.player_name,
        "role": company.role,
        "city_id": company.city_id,
        "cash": company.cash,
        "inventory": company.inventory,
    }


@app.post("/api/sessions/{session_id}/start")
async def start_session_endpoint(session_id: str) -> dict:
    """Start a lobby session. Any connected player can call this."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        start_session(session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await _broadcast_session(session_id)
    return {
        "session_id": session.session_id,
        "status": session.status,
        "started_at": session.started_at,
        "ends_at": session.ends_at,
    }


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    """Return the full session state."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump()


@app.post("/api/sessions/{session_id}/orders", status_code=201)
async def place_order_endpoint(session_id: str, body: PlaceOrderRequest) -> dict:
    """
    Place an order: buyer requests goods from seller.

    Immediately deducts seller inventory and buyer shipping cost.
    Creates a shipment with a future arrival timestamp.
    """
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        session, shipment = place_order(
            session,
            buyer_company_id=body.buyer_company_id,
            seller_company_id=body.seller_company_id,
            quantity=body.quantity,
            mode=body.transport_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await _broadcast_session(session_id)
    return {
        "shipment_id": shipment.shipment_id,
        "from_city": shipment.from_city,
        "to_city": shipment.to_city,
        "quantity": shipment.quantity,
        "transport_mode": shipment.transport_mode,
        "departs_at": shipment.departs_at,
        "arrives_at": shipment.arrives_at,
        "shipping_cost": shipment.shipping_cost,
        "status": shipment.status,
    }


@app.get("/api/sessions/{session_id}/leaderboard")
async def leaderboard_endpoint(session_id: str) -> dict:
    """Return current company rankings sorted by profit descending."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"rankings": get_leaderboard(session)}


@app.get("/api/map")
async def get_map() -> dict:
    """
    Return EU city and route data for the frontend map engine.

    Cities include lat/lon for MapLibre/Leaflet placement.
    Routes include all available transport modes with transit times and costs.
    """
    return {
        "cities": {k: v.model_dump() for k, v in EU_CITIES.items()},
        "routes": [r.model_dump() for r in EU_ROUTES],
        "upstream_role": UPSTREAM_ROLE,
        "downstream_role": DOWNSTREAM_ROLE,
    }


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws/sessions/{session_id}")
async def websocket_session(websocket: WebSocket, session_id: str) -> None:
    """
    Real-time session state stream.

    On connect: immediately sends current session state.
    Stays open; server pushes updated state after every state change.
    Client messages are ignored (read-only stream).
    """
    session = _sessions.get(session_id)
    if not session:
        await websocket.close(code=4004)
        return

    await websocket.accept()

    if session_id not in _ws_connections:
        _ws_connections[session_id] = []
    _ws_connections[session_id].append(websocket)

    # Send current state immediately on connect
    try:
        await websocket.send_text(session.model_dump_json())
    except Exception:
        _ws_connections[session_id].remove(websocket)
        return

    # Keep connection open; drain any incoming client messages
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        conns = _ws_connections.get(session_id, [])
        if websocket in conns:
            conns.remove(websocket)
