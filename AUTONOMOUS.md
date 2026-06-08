# Autonomous Work Plan — BeerGame: The Next Level

> This file is Claude's self-directed roadmap.
> Pick up from the current sprint, spawn agents, execute, commit, repeat.
> Update `## Status` after each sprint completes.
> Chris does NOT need to be present. Escalate only for: server access, budget, major pivots.

---

## Status

| Item | State |
|------|-------|
| Classic Beer Game | ✅ DONE (SHA c71ad66) |
| Logistics Wars | ✅ DONE (SHA 3b97c09) |
| CI/CD GitHub Actions | ⬜ Sprint 2 |
| PostgreSQL persistence | ⬜ Sprint 2 |
| Redis pub/sub (LW) | ⬜ Sprint 2 |
| Blockchain variant | ⬜ Sprint 3 |
| Sustainable Worlds variant | ⬜ Sprint 3 |
| Hostile Takeover variant | ⬜ Sprint 4 |
| World Disasters variant | ⬜ Sprint 4 |
| Unlimited Growth variant | ⬜ Sprint 5 |
| New Technology variant | ⬜ Sprint 5 |
| Ruthless Optimization variant | ⬜ Sprint 6 |
| Quarto reporting | ⬜ Sprint 6 |
| Ansible deploy playbooks | ⬜ Sprint 7 |
| Traefik routing per variant | ⬜ Sprint 7 |
| Mobile PWA polish | ⬜ Sprint 7 |

---

## AI Resources

### Ollama (localhost:11434) — use for code generation to save Claude tokens
```
qwen3:14b         — best all-round: code + reasoning
deepseek-r1:14b   — code + reasoning, slower
qwen3:8b          — fast tasks, boilerplate
llama3.1:8b       — fast tasks
nomic-embed-text  — embeddings only
```

### OpenRouter keys (in ~/.config/beergame/openrouter-keys.env)
```
OR_KEY_CG_VERHOEF — primary key
OR_KEY_*          — 9 more keys in GitHub secrets
```
Models on OpenRouter: `deepseek/deepseek-coder`, `qwen/qwen-2.5-coder-32b-instruct`, `anthropic/claude-3.5-haiku`

### When to use which
- Architecture design → Claude (me, Sonnet/Opus)
- Code generation (engine, API, frontend) → Ollama qwen3:14b first; OR as fallback
- Simple boilerplate / infra / Dockerfiles → Ollama qwen3:8b
- Test writing → Ollama qwen3:14b
- Never use OPENAI_API_KEY (invalid)

---

## Agent Spawn Patterns

### Standard pipeline for a new variant
Spawn ALL agents in ONE message, run_in_background:

```
1. architect  — reads CLAUDE.md + existing variants, writes spec to docs/game-design/[name].md
               → SendMessage to gearbox + canvas when done

2. gearbox    — waits for architect, reads spec, implements:
               core/engine/[name].py
               core/models/[name].py (if new models needed)
               variants/[name]/main.py
               tests/core/test_[name].py
               tests/api/test_[name]_api.py
               → SendMessage to watchdog when done

3. canvas     — waits for architect, reads spec + gearbox output, implements:
               frontend/src/routes/game/[name]/[id]/+page.svelte
               (reuse $lib/map.ts, $lib/api.ts, $lib/websocket.ts, $lib/types.ts)
               → SendMessage to watchdog when done

4. watchdog   — waits for gearbox + canvas, runs: python -m pytest tests/ && npm run build
               reports results → SendMessage to claude-lead

5. claude-lead — review, commit, update AUTONOMOUS.md status, next sprint
```

### Minimal invoke template
```javascript
Agent({ subagent_type: "system-architect", name: "architect", run_in_background: true,
  prompt: `
    Read /home/chris/Nextcloud/Github/BeerGame-TheNextLevel/CLAUDE.md and
    /home/chris/Nextcloud/Github/BeerGame-TheNextLevel/AUTONOMOUS.md for context.
    Design [VARIANT] variant mechanics. Write spec to
    docs/game-design/[name].md.
    SendMessage to 'gearbox' AND 'canvas' with the spec summary when done.
  `
})

Agent({ subagent_type: "backend-dev", name: "gearbox", run_in_background: true,
  prompt: `
    Wait for message from 'architect'.
    Use Ollama qwen3:14b via Bash (curl http://localhost:11434/api/generate) to generate code.
    Implement backend for [VARIANT]: engine, models, FastAPI, tests.
    File paths in CLAUDE.md project structure section.
    Run python -m pytest tests/ before SendMessage to 'watchdog'.
  `
})

Agent({ subagent_type: "coder", name: "canvas", run_in_background: true,
  prompt: `
    Wait for message from 'architect'.
    Implement SvelteKit frontend for [VARIANT].
    Svelte 5 syntax ONLY: onclick= not on:click=. No on: event directives.
    Use $lib/map.ts, $lib/api.ts, $lib/types.ts (extend if needed).
    Target: frontend/src/routes/game/[name]/[id]/+page.svelte
    Run: cd frontend && npm run build before SendMessage to 'watchdog'.
  `
})

Agent({ subagent_type: "tester", name: "watchdog", run_in_background: true,
  prompt: `
    Wait for messages from 'gearbox' AND 'canvas'.
    Run: python -m pytest tests/ -v && cd frontend && npm run build
    SendMessage to 'claude-lead' with pass/fail summary and any errors.
  `
})
```

---

## Sprint 2 — Infrastructure

**Goal:** Replace in-memory dicts with PostgreSQL, add Redis for LW pub/sub, wire GitHub Actions CI.

### Tasks

#### 2A — GitHub Actions CI (Haiku — fast, cheap)
File: `.github/workflows/ci.yml`
```yaml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install uv && uv pip install -r variants/classic/requirements.txt --system
      - run: python -m pytest tests/ -v
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: cd frontend && npm ci && npm run build
```

#### 2B — PostgreSQL schema (Gearbox — Ollama qwen3:14b)
- `core/db.py` — SQLAlchemy 2.x async engine setup; reads DATABASE_URL from env
- `core/models/db_classic.py` — ORM models for GameState (JSONB column for players/history)
- `core/models/db_realtime.py` — ORM models for GameSession, Company, Shipment
- Migration strategy: Alembic in `alembic/` directory
- Classic variant: swap in-memory `GAMES: dict` for DB reads/writes
- LW variant: swap `SESSIONS: dict` for DB reads/writes

#### 2C — Redis pub/sub for LW (Gearbox)
- `core/pubsub.py` — async Redis client (aioredis), publish/subscribe helpers
- LW WebSocket handler: subscribe to session channel, broadcast on state change
- `variants/realtime/main.py`: replace manual broadcast list with Redis pub/sub

#### 2D — Docker Compose updates (Pipeline — Ollama qwen3:8b)
- Add `postgres` and `redis` services to both `infra/docker/classic/docker-compose.yml` and `infra/docker/realtime/docker-compose.yml`
- Environment variables via `.env` files (already have `.env.example`)

### How to execute Sprint 2
```
Read this file. Spawn 3 agents simultaneously:
  - ci-agent: writes .github/workflows/ci.yml and .github/workflows/deploy.yml
  - gearbox: writes DB layer (core/db.py, migrations, variant updates)
  - pipeline: updates docker-compose files
Run tests after each agent completes.
Commit each piece separately.
```

---

## Sprint 3 — Blockchain + Sustainable Worlds

### Variant: Blockchain
**Mechanic:** Transparent ledger. Every order is a "smart contract" visible to ALL players.
Players can see the full order history of the entire supply chain, unlike classic where each
player only sees their own. Intended to show how transparency reduces bullwhip effect.

**Reference:** https://github.com/Hogeschool-Windesheim/blockchain-demonstrator-serious-game
Read this reference repo for mechanics — DO NOT copy code (it has bugs).

**Implementation:**
- Engine: extend `ClassicGameEngine` in `core/engine/blockchain.py`
  - Add `ledger: list[LedgerEntry]` to state (shared order history)
  - Each `advance_round()` appends all orders to ledger
  - Ledger is broadcast to ALL players (not just own stats)
- Frontend: `/game/blockchain/[id]/+page.svelte`
  - Map same as classic (5 cities)
  - Extra panel: scrollable shared ledger showing round / role / order / inventory
  - Bullwhip comparison chart: stdev of orders vs classic run

**Files to create:**
- `core/engine/blockchain.py`
- `variants/blockchain/main.py` (port 8002)
- `variants/blockchain/requirements.txt`
- `frontend/src/routes/game/blockchain/[id]/+page.svelte`
- `tests/core/test_blockchain.py`
- `tests/api/test_blockchain_api.py`
- `infra/docker/blockchain/docker-compose.yml`
- `docs/game-design/blockchain.md`

### Variant: Sustainable Worlds
**Mechanic:** Each transport decision has a CO2 cost. Faster = more CO2. Players minimize
supply chain cost AND carbon footprint. Score = weighted (financial + environmental).

**Implementation:**
- Engine: `core/engine/sustainable.py` extends realtime engine
  - Add `co2_per_unit` to each RouteMode in geography
  - `Company` gets `co2_emitted: float` field
  - Score formula: `total_profit - (co2_emitted * carbon_price_per_ton)`
  - Carbon price starts low ($10/ton), increases each round (carbon tax ratchet)
- Frontend: `/game/sustainable/[id]/+page.svelte`
  - Map shows CO2 footprint overlay (darker = more emissions)
  - Sidebar: financial P&L + CO2 footprint meter per company
  - Transport mode selector shows CO2 cost alongside time/money

**Files to create:**
- `core/engine/sustainable.py`
- `core/models/sustainable.py` (CO2-extended Company model)
- `variants/sustainable_worlds/main.py` (port 8003)
- `frontend/src/routes/game/sustainable/[id]/+page.svelte`
- `tests/core/test_sustainable.py`
- `docs/game-design/sustainable_worlds.md`

### Execution
```javascript
// Spawn 8 agents for both variants in parallel (architect → builder pipeline)
// Each variant has its own architect + gearbox + canvas + watchdog
// Total: 2 architects (parallel), then 2 gearbox + 2 canvas (parallel), then 2 watchdogs

// Step 1: spawn architects simultaneously
Agent({ name: "arch-blockchain", prompt: "Design blockchain variant per AUTONOMOUS.md Sprint 3. Write to docs/game-design/blockchain.md. SendMessage to 'gear-blockchain' AND 'canvas-blockchain'." })
Agent({ name: "arch-sustainable", prompt: "Design sustainable worlds variant per AUTONOMOUS.md Sprint 3. Write to docs/game-design/sustainable_worlds.md. SendMessage to 'gear-sustainable' AND 'canvas-sustainable'." })

// Step 2: builders wait for their architect
Agent({ name: "gear-blockchain",  prompt: "Wait for arch-blockchain. Build backend. Ollama qwen3:14b for code. SendMessage to 'watchdog-s3'." })
Agent({ name: "gear-sustainable", prompt: "Wait for arch-sustainable. Build backend. Ollama qwen3:14b. SendMessage to 'watchdog-s3'." })
Agent({ name: "canvas-blockchain",  prompt: "Wait for arch-blockchain. Build frontend. Svelte 5 syntax. SendMessage to 'watchdog-s3'." })
Agent({ name: "canvas-sustainable", prompt: "Wait for arch-sustainable. Build frontend. Svelte 5 syntax. SendMessage to 'watchdog-s3'." })

// Step 3: single watchdog waits for all 4 builders
Agent({ name: "watchdog-s3", prompt: "Wait for 4 messages (gear-blockchain, gear-sustainable, canvas-blockchain, canvas-sustainable). Run full test suite + build. Report to 'claude-lead'." })
```

---

## Sprint 4 — Hostile Takeover + World Disasters

### Variant: Hostile Takeover
**Mechanic:** Two competing supply chains on the SAME map. Players choose Team A or Team B.
Customer demand is finite — if Team A fills an order, Team B cannot. Market share tracked.
Companies can "attack" by undercutting prices (offering discount to downstream of opponent).
Bankruptcy of entire chain = game over for that team.

**Key additions vs LW:**
- `team: 'A' | 'B'` on Company
- Shared customer pool with finite demand
- `price_per_unit` on Company (can be changed each round, min 2.0, max 10.0)
- Customer chooses cheapest available supplier
- "Attack" action: offer 20% discount for 1 round (costs cash)
- Win condition: opponent team all bankrupt OR hold >70% market share for 3 consecutive ticks

**Files:**
- `core/engine/hostile_takeover.py`
- `core/models/hostile.py`
- `variants/hostile_takeover/main.py` (port 8004)
- `frontend/src/routes/game/hostile/[id]/+page.svelte`
- `tests/core/test_hostile.py`
- `docs/game-design/hostile_takeover.md`

### Variant: World Disasters
**Mechanic:** Random disruption events fire during the game. Examples:
- Port strike: Rotterdam blocked for 3 ticks (no ship routes in/out)
- Pandemic: demand doubles for 5 ticks (PPE shortage scenario)
- Fuel crisis: truck cost triples for 4 ticks
- Factory fire: one factory goes offline for 6 ticks
Players must manage resilience: diversify suppliers, hold safety stock, reroute.
Resilience score = how quickly supply chain recovers after each event.

**Key additions vs LW:**
- `DisruptionEvent` model: type, affected_entity, severity, start_tick, duration_ticks, active
- Event scheduler: random events fire at game start (seeded for fairness in multiplayer)
- Route/company availability checks in place_order
- `resilience_score` per company: time-weighted backlog during disruptions

**Files:**
- `core/engine/world_disasters.py`
- `core/models/disasters.py`
- `variants/world_disasters/main.py` (port 8005)
- `frontend/src/routes/game/disasters/[id]/+page.svelte`
  - Map: disaster overlays (red X on affected cities/routes)
  - Event log panel in sidebar
  - Resilience score display
- `tests/core/test_disasters.py`
- `docs/game-design/world_disasters.md`

---

## Sprint 5 — Unlimited Growth + New Technology

### Variant: Unlimited Growth
**Mechanic:** Companies have stock prices. Revenue → dividends (shareholder value) vs reinvestment
(capacity). Players choose split each round. Stock price = function of growth rate + dividend yield.
External "market" buys from cheapest retailer. Boom/bust cycles emerge naturally.
Win: highest stock market cap at game end.

**Key mechanics:**
- `Company.stock_price: float` — updated each tick based on earnings + growth
- `Company.shares_outstanding: int` — fixed at game start
- `Company.dividend_ratio: float` — set by player each round (0.0–1.0)
- `Company.capacity: int` — max units producible per tick; increases with reinvestment
- Market cap = stock_price × shares_outstanding
- Stock price formula: `prev_price × (1 + 0.1 × roe - 0.05 × (1 - dividend_ratio))`
  where `roe = net_income / total_equity`

**Files:**
- `core/engine/unlimited_growth.py`
- `core/models/unlimited.py`
- `variants/unlimited_growth/main.py` (port 8006)
- `frontend/src/routes/game/growth/[id]/+page.svelte`
  - Stock ticker panel showing all companies' prices over time
  - Sparkline per company
  - Dividend/reinvest slider
- `tests/core/test_unlimited_growth.py`
- `docs/game-design/unlimited_growth.md`

### Variant: New Technology
**Mechanic:** Players invest in technology upgrades that change game mechanics.
Available technologies (buy with cash):
- `erp_system` ($5000): see upstream inventory (information sharing)
- `ai_forecasting` ($8000): AI calculates optimal order for you each round
- `blockchain_orders` ($6000): instant order confirmation (removes 1-round delay)
- `green_logistics` ($4000): CO2 reduced 40%, eligible for carbon credits
- `automated_warehouse` ($7000): holding cost halved
Each tech takes 2 rounds to implement. Teaches: digital transformation ROI vs risk.

**Files:**
- `core/engine/new_technology.py` — extends classic engine with tech layer
- `core/models/tech.py` — TechUpgrade model, Company extension
- `variants/new_technology/main.py` (port 8007)
- `frontend/src/routes/game/tech/[id]/+page.svelte`
  - Tech shop panel: available upgrades, cost, effect, status
  - Chain view shows tech badges per player
- `tests/core/test_new_technology.py`
- `docs/game-design/new_technology.md`

---

## Sprint 6 — Ruthless Optimization + Quarto Reports

### Variant: Ruthless Optimization
**Mechanic:** No fixed supply chain roles. Pure free market. Any company can buy from any
other company if a route exists. Price is set by seller. Emergent supply chain structures form.
Invisible hand: customers pick cheapest retailer. Retailers pick cheapest wholesaler. Etc.
Winner: company with highest net profit. Teaches: emergent order, price signals, oligopoly.

**Key mechanics:**
- No fixed upstream/downstream — any company can trade with any other
- `Company.sell_price: float` — set by player each round
- Customers always buy from cheapest available retailer with inventory
- Companies can advertise (cost: 5% of revenue, demand bonus: +20%)
- Market transparency setting: players can see competitor prices (or not — configurable)

**Files:**
- `core/engine/ruthless.py`
- `core/models/ruthless.py`
- `variants/ruthless_optimization/main.py` (port 8008)
- `frontend/src/routes/game/ruthless/[id]/+page.svelte`
  - Market board: all sell prices visible
  - Price setter widget (slider with profit margin indicator)
  - Market share chart (pie, updated each tick)
- `tests/core/test_ruthless.py`
- `docs/game-design/ruthless_optimization.md`

### Quarto Reporting
**Goal:** Generate PDF + HTML post-game report per session.
**Files:**
- `core/reporting/report_classic.qmd` — Quarto template for classic variant
- `core/reporting/report_lw.qmd` — template for Logistics Wars
- `core/reporting/generator.py` — Python: extract game data → JSON → run quarto render
- `core/reporting/charts.py` — matplotlib/plotly chart generators for Quarto
- n8n webhook trigger: on game `status == complete`, POST to `/api/reports/generate`
- Report stored in `reports/[game_id]/report.html` + `report.pdf`

---

## Sprint 7 — Deployment + Polish

### Ansible deployment
- `infra/ansible/deploy.yml` — main playbook
- `infra/ansible/roles/` — docker, traefik, ssl, backups
- `infra/ansible/inventory/staging.ini`, `production.ini`
- Test with: `ansible-lint infra/ansible/`
- Requires: OpenVPN to Proxmox (Chris must be present for first deploy test)

### Traefik routing
- `infra/traefik/dynamic/` — one config per variant
- Pattern: `classic.valuechainhackers.xyz`, `lw.valuechainhackers.xyz`, etc.
- Auto TLS via Let's Encrypt

### Mobile PWA polish
- `frontend/static/manifest.json` — icons, theme, display: standalone
- Service worker for offline mode (basic: cache game state)
- Test on mobile: tap targets min 44px, no horizontal scroll
- Lighthouse PWA score ≥ 90

---

## Code Patterns for New Variants

### Backend engine pattern (extend existing)
```python
# core/engine/[name].py
from core.engine.game_loop import advance_round as base_advance  # or realtime
from core.models.[name] import [Name]GameState

def advance_round(state: [Name]GameState, orders: dict) -> [Name]GameState:
    """[Variant-specific] step before/after base logic."""
    # 1. Apply variant pre-processing
    state = _apply_variant_pre(state)
    # 2. Run base advance
    state = base_advance(state, orders)  # or call realtime functions
    # 3. Apply variant post-processing
    state = _apply_variant_post(state)
    return state
```

### FastAPI variant pattern
```python
# variants/[name]/main.py
from variants.classic.main import app as base_app  # only if sharing endpoints
# OR start fresh — copy variants/classic/main.py and modify

# Always include:
# GET  /health
# POST /api/games (or /api/sessions for realtime variants)
# GET  /api/games/{id}
# POST /api/games/{id}/orders
# WS   /ws/games/{id}
# GET  /api/map  (if using geography)

PORT = 800X  # unique per variant
```

### Frontend route pattern
```
frontend/src/routes/game/[variant-name]/[id]/+page.svelte

Always:
- import { initMap, addCityMarker, drawRouteLines } from '$lib/map';
- import { connectToSession } from '$lib/websocket';
- Svelte 5 syntax: onclick= not on:click=
- map.on('load', ...) before any source/layer additions
- onDestroy: wsCleanup?.(); clearInterval; map?.remove();
- Layout: map (65%) + sidebar (35%) via CSS grid
- Show game-over screen when state.status === 'complete'
```

### Test pattern
```python
# tests/core/test_[name].py
def make_engine():
    state = [Name]GameState()
    return [Name]Engine(state)

def test_initializes_correctly(): ...
def test_round_advances(): ...
def test_variant_mechanic(): ...  # the unique mechanic
def test_game_completes(): ...
```

---

## Execution Checklist (per sprint)

Before starting:
- [ ] Read AUTONOMOUS.md (this file)
- [ ] Run `python -m pytest tests/ -q` — must be green
- [ ] Run `cd frontend && npm run build` — must be clean

During:
- [ ] Spawn agents (architect first, then builders in parallel)
- [ ] Monitor agent messages
- [ ] Fix any issues that block progress

After each variant:
- [ ] Tests pass (all suites, not just new ones)
- [ ] Frontend builds clean
- [ ] No TypeScript errors
- [ ] `git add` only relevant files (no __pycache__, no .svelte-kit, no node_modules)
- [ ] Conventional commit: `feat([variant]): description`
- [ ] Update AUTONOMOUS.md status table
- [ ] `git push origin main`

---

## Port Assignments

| Variant | Backend Port |
|---------|-------------|
| Classic | 8000 |
| Logistics Wars | 8001 |
| Blockchain | 8002 |
| Sustainable Worlds | 8003 |
| Hostile Takeover | 8004 |
| World Disasters | 8005 |
| Unlimited Growth | 8006 |
| New Technology | 8007 |
| Ruthless Optimization | 8008 |

---

## Gotchas (hard-won from previous sprints)

- **Svelte 5 events**: `onclick=` / `onchange=` ALWAYS. NEVER `on:click=` / `on:change=`
- **Edit tool + tabs**: Edit tool fails matching tab-indented strings. Use Python replace script as fallback: `python3 -c "open(f).read().replace(old, new)"` pattern
- **MapLibre sources**: ALWAYS guard with `if (!map.getSource(id))` before adding
- **Pipeline timing**: factory's new `shipping_pipeline[1]` uses `order_placed` from BEFORE step 6 (previous round's order). Don't use the new order for this.
- **deepseek-r1 hallucination risk**: Do NOT use Ollama for domain research (got Beer Game rules wrong). Use Ollama for CODE GENERATION only. Research from docs/CLAUDE.md.
- **Realtime vs Classic ports**: 8000 and 8001 are separate uvicorn processes. Never mix.
- **AI factory**: in realtime variant only, `company.inventory = max(company.inventory, 500)` on every demand tick. This is intentional (prevents LW from being unplayable solo).
- **`canSubmit` in Classic**: simple `state.status === 'active' && humanRoles.length > 0`. No round-number tracking — caused blocking bug in earlier sprint.
- **Git add carefully**: never `git add .` — always list specific files. __pycache__, .svelte-kit, node_modules, build/ must NOT be committed.
- **Commit trailers**: NEVER add `Co-Authored-By: Claude` trailers. User does not want them.

---

## How to Resume This Plan

1. Read this file
2. Check git log: `git log --oneline -5`
3. Check status table above
4. Find first ⬜ sprint
5. Run the execution checklist "Before starting" items
6. Spawn agents per sprint instructions above
7. Work until ✅, update status, push, move to next sprint

When Chris is not present: proceed autonomously through as many sprints as possible.
When blocked (server access, budget, major design question): stop, document blocker in this file under `## Blockers`, wait.

---

## Blockers

_(none currently)_

---

## Architecture Decisions Log

| Decision | Rationale | Date |
|----------|-----------|------|
| In-memory dicts for MVP | Fastest to ship, swap for PostgreSQL in Sprint 2 | Sprint 1 |
| All variants share core/ engine | Prevents divergence, forces clean abstractions | Sprint 0 |
| Single SvelteKit app, route-separated | One deploy, shared components, clear boundaries | Sprint 0 |
| Realtime LW on separate port from Classic | Independent failure domain, simpler WebSocket management | Sprint 1 |
| AI factory restocks to 500 each tick | LW unplayable without upstream supplier; AI fills the gap | Sprint 1 |
