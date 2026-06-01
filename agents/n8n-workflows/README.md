# n8n Workflows

Live at: https://n8n.valuechainhackers.xyz

## Workflows

| File | Trigger | Purpose |
|------|---------|---------|
| `deploy-on-staging-merge.json` | GitHub webhook: PR merged to `staging` | SSH → Ansible deploy, post commit status |
| `agent-task-dispatcher.json` | Manual / sprint start | Read issues labeled `sprint: current`, dispatch to agents |
| `research-agent.json` | GitHub webhook: issue labeled `pipeline: research` | Ollama research → post findings, add `pipeline: planning` label |
| `test-runner.json` | GitHub webhook: push to any branch | Trigger GitHub Actions CI |
| `report-generator.json` | Webhook: game session `ended` event | Fetch session data → trigger Quarto report |
| `dependency-audit.json` | Cron: Monday 09:00 | Run `uv pip audit` + `npm audit`, file Issues for HIGH/CRITICAL |

## Importing

```bash
# Via n8n API (requires N8N_API_KEY)
curl -X POST https://n8n.valuechainhackers.xyz/api/v1/workflows \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d @deploy-on-staging-merge.json
```

## GitHub Webhooks to configure

Add these webhook URLs in `github.com/TheSocialChicken/BeerGame-TheNextLevel/settings/hooks`:

| Webhook URL | Events |
|-------------|--------|
| `https://n8n.valuechainhackers.xyz/webhook/deploy-staging-webhook` | Pull requests |
| `https://n8n.valuechainhackers.xyz/webhook/research-webhook` | Issues |
| `https://n8n.valuechainhackers.xyz/webhook/test-runner-webhook` | Pushes |
| `https://n8n.valuechainhackers.xyz/webhook/game-session-ended` | (from backend only) |

## Ollama integration

`research-agent` calls Ollama at `http://100.95.236.57:11434` (Fedora laptop, Tailscale).
Model: `llama3.1:8b`. Update `OLLAMA_URL` secret to change the host.
