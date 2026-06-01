# Agent Prompts

System prompts for each agent on the BeerGame: The Next Level team.

## How to Use

### In n8n
Load prompt content as the `system` message when calling any LLM node.
Example for Claude API:
```json
{
  "model": "claude-sonnet-4-6",
  "system": "{{ $('Read Prompt').item.json.content }}",
  "messages": [{"role": "user", "content": "{{ $json.task }}"}]
}
```

### In Claude Code (direct)
Reference the prompt file when spinning up a subagent or sub-task context.

### In ruflo swarm
Each agent maps to a `role` in ruflo's swarm config. See `agents/ruflo-config.yml`.

## Agent Roster

| File | Agent | Role | Ruflo SPARC Phase |
|------|-------|------|-------------------|
| `research.md` | Research | Information gathering | Specification (S) |
| `architect.md` | Architect | Game design specs | Specification (S) |
| `gearbox.md` | Gearbox | Backend / Python / FastAPI | Refinement (R) |
| `canvas.md` | Canvas | Frontend / SvelteKit / Maps | Refinement (R) |
| `pipeline.md` | Pipeline | DevOps / Ansible / Docker / n8n | All phases |
| `watchdog.md` | Watchdog | QA / Testing / Coverage | Completion (C) |

## Model Assignments (default)

| Agent | Primary | Cost-saving fallback |
|-------|---------|---------------------|
| Research | claude-sonnet-4-6 | OpenRouter: perplexity/sonar |
| Architect | claude-sonnet-4-6 | — |
| Gearbox | claude-sonnet-4-6 | OpenRouter: deepseek/deepseek-coder |
| Canvas | claude-sonnet-4-6 | OpenRouter: qwen/qwen-2.5-coder-32b |
| Pipeline | claude-haiku-4-5 | Ollama: qwen2.5-coder:7b |
| Watchdog | claude-haiku-4-5 | Ollama: qwen2.5-coder:7b |

## Non-Claude Models in the Swarm

The swarm supports multiple LLM providers via:
- **OpenRouter** — access to 100+ models (free tier available)
- **Ollama** — local models on Proxmox server (no API cost, private)
- **ruflo-ruvllm** plugin — smart routing between local and remote LLMs

Configure in `agents/ruflo-config.yml` → `providers` section.
