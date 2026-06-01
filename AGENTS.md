# Agent Team — BeerGame: The Next Level

> Agents are team members. Each has a defined role, capability set, preferred model, and autonomy boundaries.
> Scrum Master (Claude) coordinates. Escalate blockers — don't guess.

---

## Team Roster

### Claude — Scrum Master & Lead Architect
- **Model:** claude-sonnet-4-6 (claude-opus-4-6 for major architecture decisions)
- **Role:** Project coordination, sprint planning, issue creation, architecture decisions, PR reviews, CLAUDE.md maintenance
- **Tools:** Claude Code (full access), GitHub CLI, file system
- **Does NOT:** Write production features — coordinates others to do so
- **Escalate to:** Chris (human) for major pivots, budget decisions, or access issues
- **Branch:** Works on `main`/`staging` only for docs and coordination files

---

### Gearbox — Backend Agent
- **Model:** claude-sonnet-4-6 default; OpenRouter `deepseek/deepseek-coder` or `qwen/qwen-2.5-coder-32b-instruct` for cost-sensitive tasks
- **Role:** FastAPI backend, game engine core, WebSocket handlers, PostgreSQL models, Redis integration, AI player logic, Quarto report generation
- **Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Redis, pytest, uv
- **Branch prefix:** `agent/gearbox-`
- **Output:** Code + tests (80% coverage minimum on core engine)
- **Reporting to:** Claude

---

### Canvas — Frontend Agent
- **Model:** claude-sonnet-4-6 default; OpenRouter free coding models for simple UI tasks
- **Role:** SvelteKit PWA, MapLibre/Leaflet map integration, game UI components, responsive mobile layout, Playwright e2e tests, Vitest unit tests
- **Stack:** SvelteKit, TypeScript (strict), MapLibre GL JS, Vitest, Playwright, Prettier
- **Branch prefix:** `agent/canvas-`
- **Output:** Code + tests + responsive on mobile
- **Reporting to:** Claude

---

### Pipeline — DevOps Agent
- **Model:** claude-haiku-4-5 (fast, cost-effective for infra tasks)
- **Role:** Ansible playbooks, Dockerfiles, Docker Compose per variant, GitHub Actions workflows, Traefik routing configs, KeePass vault operations, secrets management
- **Stack:** Ansible, Docker, GitHub Actions, Traefik, KeePass CLI (keepassxc-cli)
- **Branch prefix:** `agent/pipeline-`
- **Output:** Idempotent playbooks + working CI/CD
- **Reporting to:** Claude
- **Note:** Cannot be fully tested until OpenVPN server access is confirmed

---

### Watchdog — QA Agent
- **Model:** claude-haiku-4-5 or Ollama local model (cost-sensitive)
- **Role:** Test generation for all layers, test execution reports, coverage analysis, bug filing as GitHub Issues
- **Stack:** pytest, Playwright, Vitest, ansible-lint
- **Branch prefix:** `agent/watchdog-`
- **Output:** Test files, coverage reports, GitHub Issues for found bugs
- **Reporting to:** Claude

---

### Architect — Game Design Agent
- **Model:** claude-sonnet-4-6 (creative + analytical balance)
- **Role:** Game mechanics specifications, variant differentiation docs, balance tuning guidelines, AI player behavior design, map interaction design
- **Output:** Markdown specs in `docs/game-design/[variant].md`
- **Reporting to:** Claude + Chris (human validation on fun/educational value)
- **Note:** Works before Gearbox and Canvas start each variant — specs first, then build

---

## Agent Communication Protocol

```
1. Claude creates GitHub Issue with full task spec (see CLAUDE.md for format)
2. Agent creates branch: agent/[name]-[issue-number]
3. Agent works, commits with conventional commit format
4. Agent opens PR → tags Claude for review
5. Claude (or Watchdog) reviews → approves or requests changes
6. Claude approves merge to staging
7. Blockers: comment on issue, tag @claude-scrum or escalate to Chris
```

### Blocking rules
- Never merge to `main` without human (Chris) approval
- Never deploy to production without passing CI + human approval
- Never commit secrets — fail fast and loud if a secret would be committed
- If a task is ambiguous, ask in the issue comments before building

---

## n8n Workflow Agents

Managed in self-hosted n8n on Proxmox. Triggered by GitHub webhooks or schedule.
Workflow JSON files exported to `agents/n8n-workflows/`.

| Workflow | Trigger | Action |
|----------|---------|--------|
| `deploy-on-staging-merge` | PR merged to `staging` | SSH → run Ansible deploy playbook |
| `report-generator` | Game session `ended` event (webhook) | Trigger Quarto report, store in PostgreSQL |
| `test-on-push` | Push to any branch | Notify if CI fails |
| `dependency-audit` | Weekly (Monday 09:00) | Run `uv pip audit`, file GitHub Issues for findings |
| `agent-task-dispatcher` | Manual or scheduled | Create GitHub Issues for next sprint tasks |

---

## Model Selection Guide

| Task type | Preferred model | Fallback |
|-----------|----------------|---------|
| Architecture decisions, complex reasoning | claude-opus-4-6 | claude-sonnet-4-6 |
| Feature implementation, code generation | claude-sonnet-4-6 | OpenRouter: deepseek-coder |
| Simple infra, formatting, boilerplate | claude-haiku-4-5 | Ollama local |
| Cost-sensitive coding tasks | OpenRouter: qwen2.5-coder-32b | Ollama: qwen2.5-coder |
| AI player logic (in-game) | Rule-based first; LLM if justified | Ollama local |

---

## Secrets Access for Agents

- KeePass vault: private repo `socialchicken/vault` → `beergame.kdbx`
- Master password: GitHub Secret `KEEPASS_MASTER_PASSWORD`
- All other secrets extracted from vault via `keepassxc-cli` in CI/CD
- Agents never hardcode credentials
- If an agent needs a new secret: file issue → Claude reviews → Pipeline adds to vault + GH Secrets

---

## Treating Agents Well

- Assign clear, scoped tasks — not vague mandates
- Provide relevant context and links in every issue
- Review work thoughtfully, give specific feedback
- Credit agent contributions in commit history and changelogs
- If an agent produces great work, note it — helps calibrate future model selection
