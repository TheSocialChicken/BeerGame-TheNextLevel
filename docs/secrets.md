# Secrets Management

Vault file: `beergame.kdbx` in private repo `TheSocialChicken/vault`.
Master password: GitHub Secret `KEEPASS_MASTER_PASSWORD`.

## Vault Structure

| Path | Username | Purpose |
|------|----------|---------|
| `GitHub/SERVER_HOST` | deploy | Proxmox server IP for Ansible |
| `GitHub/DEPLOY_SSH_KEY` | deploy | SSH private key for Ansible deploys (notes field) |
| `n8n/admin` | Chris@valuechainhackers.xyz | n8n admin credentials |
| `postgres/beergame` | beergame | PostgreSQL credentials |
| `redis/beergame` | beergame | Redis auth token |

## GitHub Secrets (CI/CD)

| Secret | Value source | Used by |
|--------|-------------|---------|
| `KEEPASS_MASTER_PASSWORD` | Vault master password | Ansible, CI |
| `DEPLOY_SSH_KEY` | `GitHub/DEPLOY_SSH_KEY` in vault | Ansible SSH |
| `SERVER_HOST` | `GitHub/SERVER_HOST` in vault | Ansible inventory |

## Extracting Secrets

```bash
# Read a password
echo "$KEEPASS_MASTER_PASSWORD" | keepassxc-cli show -q -a Password beergame.kdbx "postgres/beergame"

# Read notes (SSH key)
echo "$KEEPASS_MASTER_PASSWORD" | keepassxc-cli show -q -a Notes beergame.kdbx "GitHub/DEPLOY_SSH_KEY"
```

## Rules

- Never commit `.kdbx` to the main repo — vault lives in `TheSocialChicken/vault` only
- Never log or echo secret values in CI output
- Rotate secrets via vault + update GitHub Secrets — never hardcode
- Deploy SSH key is `beergame-deploy@valuechainhackers.xyz` (ed25519, no passphrase)
- Public key must be in `~/.ssh/authorized_keys` on the Proxmox server (`10.0.4.10`)
