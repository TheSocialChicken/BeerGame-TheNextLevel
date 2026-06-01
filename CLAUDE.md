# BeerGame: The Next Level — Project Bible

> This file is the authoritative reference for all agents and contributors.
> Read this before touching any code. Scrum Master (Claude) maintains it.

---

## Vision

Multi-variant serious game platform built on the classic Beer Game supply chain simulation.
Educational tool for Hogeschool Windesheim and broader audiences.
All variants share a core engine; each adds unique mechanics.
Playable on mobile and desktop (PWA). Function over form.

**Primary domain:** valuechainhackers.xyz
**GitHub org:** TheSocialChicken
**Repo:** BeerGame-TheNextLevel
**Scrum Master:** Claude (coordinates all agents, treats them as team members)

---

## Game Variants

| Variant | Core Mechanic | Status |
|---------|---------------|--------|
| Classic | Standard Beer Game, bullwhip effect | Planned |
| Blockchain | Transparent ledger, smart contract orders | Reference exists (needs fixes) |
| Sustainable Worlds | CO2/environmental impact, partial costs, visible logistics footprint | Planned |
| Hostile Takeover | Competing supply chains, bankruptcy, market share battles | Planned |
| Unlimited Growth | Stock market integration, dividends vs reinvestment | Planned |
| World Disasters | Random disruptions, crisis management, resilience metrics | Planned |
| New Technology | SAP/blockchain/AI adoption decisions and consequences | Planned |
| Ruthless Optimization | Invisible hand of the market, price mechanics, emergent behavior | Planned |

All variants support **AI players** (rule-based by default; LLM adapter optional).

---

## Tech Stack

### Choices and rationale

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend | SvelteKit + TypeScript | Lightweight PWA, excellent mobile UX, small bundle, fast |
| Maps | Leaflet.js / MapLibre GL | Real-world map engine, open-source, embeds cleanly in Svelte |
| Backend | Python 3.12 + FastAPI | Async WebSockets, trivial AI/LLM integration, clean APIs |
| Database | PostgreSQL | Complex reporting queries, reliable, audit trails, JSONB for game state |
| Cache / Realtime | Redis | Pub/sub for multiplayer, session state, game tick management |
| Reports | Quarto | Generates PDF + HTML + CSV post-game; Python-native |
| Containers | Docker + Docker Compose | One compose file per variant, independent failure domains |
| Routing | Traefik | Already in use; subdomain per variant, auto TLS |
| Deployment | Ansible | Idempotent, runs from GitHub Actions via SSH |
| CI/CD | GitHub Actions | Runs tests, triggers Ansible playbooks |
| Secrets | KeePass + GitHub Secrets | Vault in private repo; master password in GH Secret |
| Agent workflows | n8n (self-hosted on Proxmox) | External triggers: webhooks, schedules, integrations |
| Agent orchestration | Ruflo (Claude Code meta-harness) | Internal swarm coordination, RAG memory, SPARC pipeline, multi-LLM routing |
| Package mgmt (Python) | uv | Fast, modern, reproducible |
| Package mgmt (Node) | npm | Standard, well-supported |

### Architecture overview

```
Browser (SvelteKit PWA)
    MapLibre/Leaflet (real-world map engine)
         |
    WebSocket + REST
         |
FastAPI Backend (Python)
    Game Engine Core  <--  Variant Plugin
    AI Player Layer
         |
    PostgreSQL + Redis
         |
    Quarto Report Generator

─── Agent Layer ───────────────────────────────────
Ruflo Swarm (internal coordination)
  ├── Multi-LLM routing: Claude / OpenRouter / Ollama
  ├── RAG memory (cross-session, shared across agents)
  ├── SPARC pipeline: Spec → Pseudocode → Arch → Refine → Complete
  └── Federation: dev machine ↔ server machine

n8n (external triggers)
  ├── GitHub webhooks → deploy pipeline
  ├── Game session events → report generation
  └── Scheduled audits (weekly deps, security)
```

### SPARC Pipeline (Ruflo)

Our 6-stage agent pipeline maps to Ruflo's SPARC methodology:

| Stage | Pipeline Step | SPARC | Agent |
|-------|--------------|-------|-------|
| 1 | Research | Specification (S) | Research |
| 2 | Planning | Pseudocode + Architecture (P+A) | Architect + Claude |
| 3 | Development | Refinement (R) | Gearbox + Canvas |
| 4 | Acceptance | Refinement validation (R) | Claude |
| 5 | Testing | Completion (C) | Watchdog |
| 6 | Feedback | Completion report (C) | Pipeline + Quarto |

---

## Repository Structure

```
BeerGame-TheNextLevel/
├── CLAUDE.md                  <- Project bible (you are here)
├── AGENTS.md                  <- Agent team roster and protocols
├── README.md
├── core/                      <- Shared game engine (all variants import this)
│   ├── engine/                <- Game loop, state machine, order processing
│   ├── models/                <- Pydantic models shared across variants
│   ├── ai_players/            <- AI player strategies (rule-based + LLM adapter)
│   └── reporting/             <- Quarto report templates and generators
├── variants/
│   ├── classic/
│   ├── blockchain/
│   ├── sustainable_worlds/
│   ├── hostile_takeover/
│   ├── unlimited_growth/
│   ├── world_disasters/
│   ├── new_technology/
│   └── ruthless_optimization/
├── frontend/                  <- Single SvelteKit PWA (all variants, route-separated)
│   └── src/
│       ├── lib/core/          <- Shared UI components
│       ├── lib/maps/          <- Map engine integration
│       └── routes/            <- Per-variant routes
├── infra/
│   ├── ansible/               <- Deployment playbooks
│   │   └── inventory/         <- staging.ini, production.ini
│   ├── docker/                <- Dockerfiles + per-variant compose files
│   └── traefik/               <- Dynamic routing configs
├── agents/
│   ├── n8n-workflows/         <- Exported n8n workflow JSONs
│   └── prompts/               <- Agent system prompts
├── docs/
│   ├── game-design/           <- Variant mechanics specs (Game Design Agent output)
│   └── adr/                   <- Architecture Decision Records
└── .github/
    └── workflows/
        ├── ci.yml             <- Tests on every push/PR
        └── deploy.yml         <- Deploy to staging/production via Ansible
```

---

## Architecture Principles

1. **Core first** — No variant ships without core engine test coverage at 80%+
2. **Variant = extension** — Variants import core, never fork it
3. **Independent deployment** — Each variant has its own Docker Compose, own subdomain
4. **No shared runtime state between variants** — PostgreSQL schemas are variant-namespaced
5. **AI players are pluggable** — Default is rule-based; LLM adapter is optional per game
6. **Reporting is async** — Reports generated post-game, never block gameplay
7. **Secrets via vault** — No hardcoded credentials anywhere. Period.
8. **Tests gate deployment** — CI must be green before any deploy runs
9. **Agents are team members** — Treat them with the same respect as human contributors

---

## Coding Conventions

### Python (backend, core engine)
- Python 3.12+, managed with `uv`
- Pydantic v2 for all data models
- Type hints required on all public functions
- `async` by default (FastAPI)
- Tests in `tests/` using pytest; aim for 80%+ coverage on core
- `ruff` for linting, `black` for formatting
- Docstrings on all public functions and classes

### TypeScript / Svelte (frontend)
- SvelteKit with TypeScript strict mode
- No `any` types
- Vitest for unit tests, Playwright for e2e
- Prettier for formatting
- Components in `$lib/`, routes in `src/routes/`

### General
- No magic numbers — use named constants
- Environment variables via `.env` (never committed)
- Secrets via GitHub Secrets or KeePass vault only
- Conventional commits: `type(scope): description`
  - Types: `feat`, `fix`, `test`, `docs`, `infra`, `refactor`, `chore`

---

## Git Workflow

```
main          <- stable, deployed to production
  └── staging <- integration; auto-deploys to staging environment
       └── feature/[variant]-[short-description]
       └── fix/[short-description]
       └── agent/[agent-name]-[issue-number]
```

- Branch from `staging`, PR back to `staging`
- Staging → main requires manual approval (Chris or Claude)
- Commit format: `feat(classic): add order processing state machine`
- PRs require passing CI and at least one review (Claude counts)

---

## Testing Requirements

| Layer | Tool | Minimum |
|-------|------|---------|
| Core engine unit tests | pytest | 80% coverage |
| API integration tests | pytest + httpx | All endpoints |
| WebSocket tests | pytest + websockets | Connect, message, disconnect |
| Frontend unit | Vitest | All utility functions |
| E2E full game flow | Playwright | One full game per variant |
| Ansible syntax | ansible-lint | All playbooks |

CI blocks merge on any test failure.

---

## Deployment

### Subdomain routing via Traefik

| Environment | Subdomain pattern |
|-------------|-------------------|
| Production | `[variant].valuechainhackers.xyz` |
| Staging | `staging-[variant].valuechainhackers.xyz` |

### Deploy process

1. Push to `staging` branch triggers GitHub Actions
2. CI runs full test suite
3. On pass: GitHub Actions SSHs to Proxmox server
4. Runs Ansible playbook `infra/ansible/deploy.yml`
5. Ansible builds Docker image, updates Compose, restarts container
6. Traefik detects new container via labels, routes traffic
7. Health check confirms deploy

### Infrastructure references
- Ansible base playbooks: https://github.com/Windesheim-A-I-Support/InstallLocalAiPackage
- Proxmox host: access via OpenVPN (from designated machine only)
- n8n: self-hosted on Proxmox, already running

---

## Secrets Management

- **KeePass vault** (`.kdbx`) stored in private repo `socialchicken/vault`
- **Master password** stored in GitHub Secret `KEEPASS_MASTER_PASSWORD`
- **Deploy SSH key** stored in GitHub Secret `DEPLOY_SSH_KEY`
- **Server host** stored in GitHub Secret `SERVER_HOST`
- All agents access secrets via environment variables injected by CI/CD
- Never log, print, echo, or commit secret values
- Vault password rotated if ever exposed in chat/logs

---

## Scrum Process

**Scrum Master:** Claude
**Sprint length:** 1 week (AI-paced, flexible)
**Task tracking:** GitHub Issues + GitHub Projects
**Branch strategy:** agents create `agent/[name]-[issue-number]` branches

### Task format for agents

```
Title: [AGENT] Short description of task
Labels: backend | frontend | infra | testing | design
Body:
  ## Goal
  One sentence.

  ## Acceptance Criteria
  - [ ] Criterion 1
  - [ ] Criterion 2

  ## Files to touch
  - path/to/file.py

  ## Dependencies
  - Closes #N / Depends on #N

  ## Notes for agent
  Any constraints, gotchas, links to relevant docs.
```

### Sprint cadence

1. Claude reviews backlog, creates sprint issues
2. Agents pick up issues, create branches
3. Agents open PRs when done
4. Claude (+ Watchdog) reviews, approves or requests changes
5. Merged to staging, tested
6. End of sprint: Claude updates CLAUDE.md with lessons learned

---

## Reference Material

- Original blockchain variant (has bugs, good reference): https://github.com/Hogeschool-Windesheim/blockchain-demonstrator-serious-game
- Ansible/infra playbooks: https://github.com/Windesheim-A-I-Support/InstallLocalAiPackage
- Beer Game theory: Sterman (1989), MIT original
- Quarto documentation: https://quarto.org/docs/
- MapLibre GL JS: https://maplibre.org/maplibre-gl-js/docs/
