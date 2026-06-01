# Agent Infrastructure Setup

## Step 1 — Install Ruflo (both machines)

```bash
# Full install — gives complete loop: 98 agents, MCP server, hooks, daemon
npx ruflo init

# Then install project plugins (in repo root):
/plugin install ruflo-core@ruflo
/plugin install ruflo-swarm@ruflo
/plugin install ruflo-rag-memory@ruflo
/plugin install ruflo-goals@ruflo
/plugin install ruflo-sparc@ruflo
/plugin install ruflo-workflows@ruflo
/plugin install ruflo-intelligence@ruflo
/plugin install ruflo-adr@ruflo
/plugin install ruflo-testgen@ruflo
/plugin install ruflo-browser@ruflo
/plugin install ruflo-security-audit@ruflo
/plugin install ruflo-cost-tracker@ruflo
/plugin install ruflo-ruvllm@ruflo
/plugin install ruflo-federation@ruflo
```

## Step 2 — Configure Ruflo

Copy `agents/ruflo-config.yml` as your ruflo project config.
Update `federation.nodes[1].host` with actual server IP after OpenVPN access.

## Step 3 — Install Claude Code Skills

These skills provide specialized knowledge to agents. Install globally:

```bash
# Core skills for this project
# (run in Claude Code via /skill install or settings)

# Multi-agent coordination
multi-agent-patterns
agent-orchestrator
agents-md

# Backend
fastapi-pro
python-pro
python-testing-patterns

# Frontend
sveltekit          # if available
react-patterns     # fallback
playwright-skill

# DevOps
ansible            # if available
docker-expert
github-actions-templates

# Game
game-development

# Workflow
n8n-workflow-patterns
n8n-mcp-tools-expert

# Quality
prompt-engineering
code-review-excellence
```

## Step 4 — Connect OpenRouter

Add to your environment or GitHub Secrets:
```
OPENROUTER_API_KEY=your_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

## Step 5 — Configure Ollama on Server (after OpenVPN access)

```bash
# On Proxmox server:
ollama pull qwen2.5-coder:7b
ollama pull llama3.2:3b

# Expose on LAN (Traefik will route):
OLLAMA_HOST=0.0.0.0 ollama serve
```

## Step 6 — Set up Federation

After both machines have ruflo running:
```bash
# On server machine:
npx ruflo federation register --name server-machine --role deployment,testing,local_llm

# On dev machine:
npx ruflo federation connect --peer server-machine --host [server-ip]
```

## Notes

- Server machine handles: deployment (Ansible), local LLM (Ollama), n8n triggers
- Dev machine handles: planning, code generation, review, architecture
- Both machines share memory via ruflo-rag-memory (synced)
- n8n remains the external trigger layer (webhooks, schedules)
- ruflo handles the internal agent coordination (swarm, memory, routing)
