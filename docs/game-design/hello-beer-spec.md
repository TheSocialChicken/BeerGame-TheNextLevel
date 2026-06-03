# Hello Beer — Technical Specification

**Variant:** Classic (minimal proof-of-concept)
**Version:** 0.1.0
**Status:** Implementation complete, pipeline validation target

---

## 1. Overview

Hello Beer is the minimal playable implementation of the Classic Beer Game on this platform. Its
purpose is not feature completeness — it is a pipeline test. A successful Hello Beer run proves
that the backend engine, WebSocket layer, REST API, and SvelteKit frontend are all wired together
and that a full 26-round game can be played end-to-end with real or AI players.

Every other variant on this platform will be built on top of the same core engine and API
conventions validated here. Hello Beer is the canary: if it breaks, something foundational is
broken.

**What Hello Beer demonstrates:**

- Four-role supply chain simulation running to completion
- WebSocket real-time updates between server and browser clients
- REST API for session creation and scoreboard retrieval
- AI players filling any un-joined role automatically
- Per-round cost accrual and a final scoreboard

**What Hello Beer deliberately omits:**

- Persistent storage (in-memory only, state lost on restart)
- Authentication or user accounts
- Map rendering
- Blockchain ledger
- Variant-specific mechanics (CO2, bankruptcy, market price, etc.)
- Quarto report generation

---

## 2. Architecture

```
Browser (SvelteKit PWA)
  /                  — lobby: create session, copy join URLs
  /game/{id}/{role}  — game board: inventory, backlog, order form, cost ticker

         |  HTTP REST    |  WebSocket
         v               v

variants/classic/app.py  (FastAPI, title="Classic Beer Game")
  POST /sessions                  — create session, return join URLs
  GET  /sessions/{id}/scoreboard  — final scores and demand history

backend/api/games.py  (mounted under /games)
  POST /games/                    — create game with config + ai_roles
  POST /games/{id}/start          — transition WAITING -> ACTIVE
  POST /games/{id}/orders         — submit one order (REST path)
  GET  /games/{id}/state          — full or role-filtered state

backend/api/websocket.py  (mounted at /ws)
  WS   /ws/{game_id}/{role}       — persistent connection per player

backend/services/game_store.py   — in-memory dict[str, GameState]
backend/services/connection_manager.py — WebSocket connection registry

core/engine/game_engine.py       — create_game, start_game, submit_order, process_round
core/engine/order_processor.py   — advance_shipments, fulfill_orders, place_orders, accrue_costs
core/models/game.py              — GameState, GameConfig, PlayerState, GamePhase
core/models/player.py            — PlayerRole enum
core/models/order.py             — IncomingShipment
core/ai_players/rule_based.py    — OrderUpToAI, ConstantOrderAI
```

Orders can be submitted via either the REST endpoint (`POST /games/{id}/orders`) or the WebSocket
(`{"action": "order", "quantity": N}`). Both paths call the same engine method and trigger the
same round-advance logic when all orders are collected.

---

## 3. Data Models

### 3.1 GameConfig

Defined in `core/models/game.py`. All fields have defaults matching the standard Beer Game
parameters.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `num_rounds` | `int` | `26` | Total rounds in the game |
| `initial_inventory` | `int` | `12` | Starting inventory for every role |
| `initial_backlog` | `int` | `0` | Starting backlog for every role |
| `demand_pattern` | `list[int]` | `[4]*4 + [8]*22` | Customer demand per round (retailer only) |
| `holding_cost` | `float` | `0.50` | Cost per unit held in inventory per round |
| `backlog_cost` | `float` | `1.00` | Cost per unit of unmet backlog per round |
| `shipping_delay` | `int` | `2` | Rounds for a shipment to travel one hop |
| `order_delay` | `int` | `2` | Rounds for an order to reach the supplier |

### 3.2 PlayerState

| Field | Type | Description |
|-------|------|-------------|
| `role` | `PlayerRole` | One of `retailer`, `wholesaler`, `distributor`, `factory` |
| `inventory` | `int` | Units currently on hand (>= 0) |
| `backlog` | `int` | Units of unmet demand carried forward (>= 0) |
| `incoming_shipments` | `list[IncomingShipment]` | Pipeline: shipments in transit with arrival countdown |
| `incoming_orders` | `list[int]` | Order queue from the downstream role |
| `last_order` | `int` | Quantity ordered in the most recent round |
| `cumulative_cost` | `float` | Total cost accrued across all rounds so far |
| `is_ai` | `bool` | Whether this role is controlled by an AI player |

`PlayerState.round_cost()` computes the per-round charge:
`inventory * 0.50 + backlog * 1.00`

### 3.3 GameState

| Field | Type | Description |
|-------|------|-------------|
| `game_id` | `str` | UUID4 assigned at creation |
| `variant` | `str` | Always `"classic"` for this variant |
| `phase` | `GamePhase` | `waiting`, `active`, or `finished` |
| `current_round` | `int` | Zero-indexed round counter (0 before game starts) |
| `config` | `GameConfig` | Game parameters (see above) |
| `players` | `dict[PlayerRole, PlayerState]` | State for each of the four roles |
| `customer_demand_history` | `list[int]` | Demand values seen so far (appended each round) |
| `orders_this_round` | `dict[PlayerRole, int]` | Orders collected for the current round (cleared after processing) |

`GameState.is_round_complete()` returns `True` when every non-AI role has submitted an order for
the current round.

`GameState.total_cost()` returns the sum of `cumulative_cost` across all four players.

### 3.4 GamePhase

| Value | Meaning |
|-------|---------|
| `waiting` | Game created, waiting for `start` call |
| `active` | Game running, accepting orders |
| `finished` | All 26 rounds complete |

### 3.5 PlayerRole

Roles in supply chain order (upstream to downstream):

```
factory -> distributor -> wholesaler -> retailer -> (customer demand)
```

Enum values (string): `retailer`, `wholesaler`, `distributor`, `factory`.

### 3.6 IncomingShipment

| Field | Type | Description |
|-------|------|-------------|
| `quantity` | `int` | Units in this shipment |
| `arrives_in_rounds` | `int` | Rounds remaining until this shipment arrives |

At game creation each role's pipeline is pre-filled with `shipping_delay` shipments of
`initial_inventory // 2` units each (i.e. two shipments of 6 units for the default config).

---

## 4. REST API Endpoints

### 4.1 POST /sessions

Creates a new Classic game session with the default config and no AI players pre-assigned.

**Request:** No body.

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "join_urls": {
    "retailer":     "/ws/{session_id}/retailer",
    "wholesaler":   "/ws/{session_id}/wholesaler",
    "distributor":  "/ws/{session_id}/distributor",
    "factory":      "/ws/{session_id}/factory"
  }
}
```

**Notes:** The session starts in `waiting` phase. Players connect via the returned WebSocket URLs.
The game does not advance until `POST /games/{id}/start` is called.

---

### 4.2 GET /sessions/{session_id}/scoreboard

Returns cumulative scores and demand history. Available at any game phase; most useful after
`finished`.

**Response:**
```json
{
  "session_id": "550e8400-...",
  "round": 26,
  "phase": "finished",
  "scores": {
    "retailer":     142.50,
    "wholesaler":   198.00,
    "distributor":  87.00,
    "factory":      213.50
  },
  "demand_history": [4, 4, 4, 4, 8, 8, ...]
}
```

**Error:** `404` if `session_id` not found.

---

### 4.3 POST /games/

Creates a game with explicit config and AI role assignment.

**Request body:**
```json
{
  "config": { "num_rounds": 26, "initial_inventory": 12, ... },
  "ai_roles": ["wholesaler", "distributor", "factory"]
}
```

**Response (201):**
```json
{
  "game_id": "...",
  "phase": "waiting",
  "config": { ... }
}
```

---

### 4.4 POST /games/{game_id}/start

Transitions the game from `waiting` to `active`. Also broadcasts a `game_started` event to all
connected WebSocket clients.

**Response:**
```json
{ "game_id": "...", "phase": "active" }
```

**Errors:**
- `404` — game not found
- `400` — game is not in `waiting` phase

---

### 4.5 POST /games/{game_id}/orders

Submits an order for a role via REST (alternative to the WebSocket path).

**Request body:**
```json
{ "role": "retailer", "quantity": 8 }
```

**Response:**
```json
{ "game_id": "...", "round": 1, "phase": "active" }
```

When this order completes the round (i.e. all non-AI roles have now submitted), the server
automatically fills any remaining AI orders and calls `process_round()`, then broadcasts
`round_complete` or `game_over` to all WebSocket connections.

**Errors:**
- `404` — game not found
- `400` — game not active, invalid role, negative quantity

---

### 4.6 GET /games/{game_id}/state

Returns the current game state. If `role` query param is provided, returns only that role's
visible state (hides other players' inventory/backlog).

**Without role param:**
```json
{
  "game_id": "...",
  "phase": "active",
  "round": 3,
  "total_cost": 72.00,
  "connected_roles": ["retailer", "wholesaler"]
}
```

**With `?role=retailer`:**
```json
{
  "game_id": "...",
  "round": 3,
  "phase": "active",
  "role": "retailer",
  "inventory": 10,
  "backlog": 0,
  "last_order": 8,
  "cumulative_cost": 18.00,
  "incoming_shipments": [
    {"quantity": 6, "arrives_in_rounds": 1},
    {"quantity": 6, "arrives_in_rounds": 2}
  ]
}
```

**Error:** `404` if game not found.

---

### 4.7 GET /games/

Lists all active game IDs.

**Response:**
```json
{ "game_ids": ["550e8400-...", "661f9511-..."] }
```

---

## 5. WebSocket Protocol

### 5.1 Connection

```
WS /ws/{game_id}/{role}
```

`role` must be one of `retailer`, `wholesaler`, `distributor`, `factory`.

**On successful connect**, the server immediately sends the role's current visible state:
```json
{
  "event": "connected",
  "game_id": "...",
  "round": 0,
  "phase": "waiting",
  "role": "retailer",
  "inventory": 12,
  "backlog": 0,
  "last_order": 0,
  "cumulative_cost": 0.0,
  "incoming_shipments": [
    {"quantity": 6, "arrives_in_rounds": 1},
    {"quantity": 6, "arrives_in_rounds": 2}
  ]
}
```

**Close codes:**
- `4000` — invalid role string
- `4004` — game_id not found

### 5.2 Client -> Server Messages

**Submit order:**
```json
{ "action": "order", "quantity": 8 }
```

**Request current state:**
```json
{ "action": "get_state" }
```

### 5.3 Server -> Client Events

All server messages include an `"event"` field.

#### `order_accepted`
Sent to the submitting client immediately after their order is recorded.
```json
{ "event": "order_accepted", "quantity": 8 }
```

#### `round_complete`
Broadcast to all connected clients after a round is processed and the game is still active.
```json
{
  "event": "round_complete",
  "round": 4,
  "phase": "active",
  "total_cost": 144.00
}
```

#### `game_over`
Broadcast to all connected clients when the final round completes.
```json
{
  "event": "game_over",
  "round": 26,
  "phase": "finished",
  "total_cost": 641.50
}
```

#### `state`
Response to a `get_state` action. Contains the role's visible state (same structure as the
`connected` event, without the `event` key remap).
```json
{
  "event": "state",
  "game_id": "...",
  "round": 5,
  "phase": "active",
  "role": "retailer",
  "inventory": 4,
  "backlog": 2,
  "last_order": 10,
  "cumulative_cost": 32.00,
  "incoming_shipments": [...]
}
```

#### `game_started`
Broadcast when `POST /games/{id}/start` is called via REST.
```json
{ "event": "game_started", "round": 0 }
```

#### `error`
Sent to the submitting client when their action is rejected.
```json
{ "event": "error", "message": "Order quantity cannot be negative" }
```

---

## 6. Game Flow

```
1. Create session
   POST /sessions
   <- { session_id, join_urls }

2. Players connect (up to 4 humans; un-joined roles remain unassigned)
   WS /ws/{session_id}/retailer
   WS /ws/{session_id}/wholesaler
   ...
   <- { event: "connected", ... }

3. Start the game
   POST /games/{session_id}/start
   -> broadcast { event: "game_started", round: 0 }

4. Each active round:
   a. Human players read their visible state (inventory, backlog, incoming shipments)
   b. Each human submits an order:
      WS send: { action: "order", quantity: N }
      WS recv: { event: "order_accepted", quantity: N }
   c. When the last human order arrives, the server:
      i.  Collects AI orders via OrderUpToAI.decide_order() for any is_ai roles
      ii. Calls process_round():
          - advance_shipments(): decrement arrival counters, deliver arrived stock
          - fulfill_orders(): satisfy downstream demand from inventory, remainder to backlog
          - place_orders(): route each role's order upstream into the supplier's order queue
          - accrue_costs(): charge holding + backlog costs, add to cumulative_cost
      iii. Increments current_round
      iv. Broadcasts round_complete (or game_over if current_round == num_rounds)

5. Repeat step 4 for rounds 1–26

6. Game ends
   -> broadcast { event: "game_over", round: 26, phase: "finished", total_cost: X }
   GET /sessions/{session_id}/scoreboard  <- per-role cumulative costs + demand history
```

### Round processing detail

Within `process_round()` the order of operations matters:

1. **advance_shipments** — each in-transit shipment has its `arrives_in_rounds` decremented; any
   shipment reaching 0 is moved into the role's inventory.
2. **fulfill_orders** — the retailer fulfills customer demand (from `demand_pattern`); each
   upstream role fulfills the order placed by the role below it. Shortfall becomes backlog.
3. **place_orders** — each role's submitted order quantity is appended to the supplier's
   `incoming_orders` queue and recorded as a new `IncomingShipment` with `arrives_in_rounds =
   shipping_delay`.
4. **accrue_costs** — `round_cost()` is computed for each role and added to `cumulative_cost`.

---

## 7. AI Player Strategy

### OrderUpToAI

Source: `core/ai_players/rule_based.py`

Constants:
- `TARGET_INVENTORY = 12`
- `SAFETY_STOCK = 4`

Decision formula applied each round:

```python
pipeline  = sum(s.quantity for s in player_state.incoming_shipments)
position  = inventory - backlog + pipeline
target    = TARGET_INVENTORY + SAFETY_STOCK   # = 16
order     = max(0, target - position)
```

The AI orders whatever is needed to bring its inventory position (on-hand minus backlog, plus
in-transit stock) up to the target of 16 units. If the position already meets or exceeds the
target, it orders zero.

### ConstantOrderAI

Orders a fixed quantity every round regardless of state. Default quantity is 4. Used as a naive
baseline for comparison, not in default Hello Beer sessions.

---

## 8. Scope Limitations

The following are explicitly out of scope for Hello Beer and will be addressed in later variants
or infrastructure milestones:

| Limitation | Notes |
|-----------|-------|
| **No persistence** | `game_store` is an in-memory dict. Server restart destroys all sessions. PostgreSQL integration is planned for the Classic 1.0 milestone. |
| **No authentication** | Any client that knows a `game_id` and a valid role string can connect. No tokens, no user accounts, no session ownership. |
| **No map rendering** | MapLibre/Leaflet integration is planned for Sustainable Worlds and logistics-visible variants. |
| **No blockchain ledger** | The Blockchain variant adds transparent order history via smart contract. Hello Beer has no on-chain state. |
| **No real-time demand visibility** | Each role sees only its own state. Upstream inventory and order queues are hidden (faithful to original Beer Game design). |
| **No Quarto reports** | Post-game PDF/HTML report generation is a planned feature. The scoreboard endpoint provides raw data as a stopgap. |
| **No Redis pub/sub** | The connection manager uses an in-process WebSocket registry. Redis is required for multi-process or multi-container deployments. |
| **No variant-specific mechanics** | CO2 costs, bankruptcy triggers, market pricing, and disruption events are all variant-layer features not present here. |
| **Single Docker Compose** | Hello Beer ships as one compose service. Multi-service orchestration and Traefik subdomain routing are infra milestones. |
