# AGENTS.md — Bibz SSH Bot (Discord)

## Run commands

```bash
pip install -r requirements.txt
python setup_bot.py          # main entry point
python test_deploy.py        # diagnostic launcher
```

Script: `./run.sh` (auto-creates venv)

## Environment

No `.env` needed — token is hardcoded in `setup_bot.py`.
- `GUILD_ID` is hardcoded to `None` (no server restriction).

## Railway Deployment

- **Platform:** Railway.app — Nixpacks builder (auto-detects Python via `requirements.txt`)
- **Config:** `railway.json` in repo root
- **Start command:** `python setup_bot.py` (set via Railway API)
- **No env vars needed** — token is in the script.

### Railway gotchas
- `setup.py` **must be renamed** (e.g. `legacy_setup.py`) — Nixpacks confuses it with a package setup script and the deployment crashes.
- `Dockerfile` + `docker-compose.yml` removed — Nixpacks only.
- No Docker needed; Railway builds and runs directly.
- Logs accessible via Railway Dashboard web UI.
- Deploy via `serviceInstanceDeployV2` mutation (pass `commitSha` explicitly).
- Railway API token: `6eb9ebc4-2947-4f86-9376-06cd644088c6`
- Project ID: `d7abe167-df09-42bd-9f35-c6181260b772`
- Service ID: `7c2659fe-f86b-4849-97d4-8a53b8546917`
- Environment ID: `d74a499a-b8ef-473a-9455-e578899d56fc`

### Deploy command
```bash
curl -s -H "Authorization: Bearer 6eb9ebc4-2947-4f86-9376-06cd644088c6" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"mutation { serviceInstanceDeployV2(serviceId: \\\"7c2659fe-f86b-4849-97d4-8a53b8546917\\\", environmentId: \\\"d74a499a-b8ef-473a-9455-e578899d56fc\\\", commitSha: \\\"$(git rev-parse HEAD)\\\") }\"}" \
  "https://backboard.railway.app/graphql/v2"
```

## Architecture

| File | Role |
|---|---|
| `setup_bot.py` | Main bot — commands, `ServerSetup` class, Discord client |
| `server_config.py` | Default ai-dev template data (categories, roles, messages) |
| `templates.py` | Template registry + `get_template()`/`list_templates()` |
| `extended_templates.py` | 10 additional community templates + `bibz-ssh` template |
| `template_scaler.py` | Scale templates by % (1–100) |
| `template_utils.py` | Preview/diff/format helpers |
| `server_manager.py` | VPS registry + asyncssh executor + account management |
| `setup_scripts.py` | Bash install scripts for SSH/Xray/WireGuard/OpenVPN/SlowDNS |
| `test_deploy.py` | Railway diagnostic launcher |
| `legacy_setup.py` | Old `setup.py` (nextcord) — renamed to avoid Nixpacks conflict |

- Core templates: `ai-dev`, `aws-chatops`, `itil-ops` (in `templates.py`)
- Extended templates: `school`, `small-business`, `gaming-hangout`, `content-creator`, `nonprofit`, `fitness`, `music-band`, `book-club`, `podcast`, `esports`, `bibz-ssh` (in `extended_templates.py`)
- All bot-created channels/roles get the `[DSBOT]` marker (channel topic, role name).
- 14 templates total.

## Commands (prefix `!`)

All require Administrator permissions.

### Server Setup (Discord channels, roles, permissions)

| Command | Example |
|---|---|
| `!setup [template] [scale]` | `!setup school 50` |
| `!preview [template] [scale]` | `!preview aws-chatops 75` |
| `!templates` | list all |
| `!status` | server state |
| `!rescale <template> <scale>` | diff preview |
| `!cleanup [channel-name]` | remove bot content |
| `!remove-channel <name>` | force delete any channel |
| `!add-channel <type> <name> [category]` | add tracked channel |
| `!add-category <name>` | add untracked category |
| `!check-detection` | show what cleanup will delete |
| `!migrate-markers` | add `[DSBOT]` to legacy channels |

### VPS / VPN Management

| Command | Example |
|---|---|
| `!add-server <name> <host> [port]` | `!add-server vps1 192.168.1.1 22` |
| `!remove-server <name>` | `!remove-server vps1` |
| `!list-servers` | list registered VPS |
| `!setup-server <name>` | install all services on VPS |
| `!add-ssh <server> <user> <pass>` | `!add-ssh vps1 alice pass123` |
| `!add-vmess <server> <user>` | `!add-vmess vps1 alice` |
| `!add-wireguard <server> <user>` | `!add-wireguard vps1 alice` |
| `!add-openvpn <server> <user>` | `!add-openvpn vps1 alice` |
| `!add-slowdns <server> <user>` | `!add-slowdns vps1 alice` |
| `!list-users <server>` | show all SSH users on server |
| `!remove-user <server> <user> [service]` | `!remove-user vps1 alice ssh` |

### Utility

| Command | Example |
|---|---|
| `!shutdown` | stop bot |
| `!help` | list commands |

## Important gotchas

- **No tests, no linting, no typechecking.** None configured. Manual testing only.
- **`discord.py>=2.0` intents required** in code + Discord Developer Portal:
  - `message_content`, `guilds`, `members` (code)
  - Enable Presence, Server Members, Message Content Intent (portal)
