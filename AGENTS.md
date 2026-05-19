# AGENTS.md — Discord Server Setup Bot

## Run commands

```bash
pip install -r requirements.txt
python setup_bot.py          # main entry point
```

Docker: `docker-compose up --build`  
Script: `./run.sh` (auto-creates venv)

## Environment

`.env` file required:
```
DISCORD_BOT_TOKEN=<token>
GUILD_ID=<optional, restrict to one server>
```

- `setup.py` also reads `DISCORD_TOKEN` as fallback; `setup_bot.py` reads only `DISCORD_BOT_TOKEN`.
- `.env` is gitignored; never commit secrets.

## Important gotchas

- **`setup.py` is NOT the main bot.** It's a separate/alternative file using `nextcord` (not `discord.py`). The real entrypoint is `setup_bot.py`.
- **Dockerfile is incomplete.** It only copies `setup_bot.py` and `server_config.py` — missing `templates.py`, `extended_templates.py`, `template_scaler.py`, `template_utils.py`. Docker builds will fail at runtime if any non-`ai-dev` template is used.
- **No tests, no linting, no typechecking.** None configured. Manual testing only.
- **`discord.py>=2.0` intents required** in code + Discord Developer Portal:
  - `message_content`, `guilds`, `members` (code)
  - Enable Presence, Server Members, Message Content Intent (portal)

## Architecture

| File | Role |
|---|---|
| `setup_bot.py` | Main bot — commands, `ServerSetup` class, Discord client |
| `server_config.py` | Default ai-dev template data (categories, roles, messages) |
| `templates.py` | Template registry + `get_template()`/`list_templates()` |
| `extended_templates.py` | 10 additional community templates |
| `template_scaler.py` | Scale templates by % (1–100) |
| `template_utils.py` | Preview/diff/format helpers |

- Core templates: `ai-dev`, `aws-chatops`, `itil-ops` (in `templates.py`)
- Extended templates: `school`, `small-business`, `gaming-hangout`, `content-creator`, `nonprofit`, `fitness`, `music-band`, `book-club`, `podcast`, `esports` (in `extended_templates.py`)
- All bot-created channels/roles get the `[DSBOT]` marker (channel topic, role name).
- 13 templates total.

## Commands (prefix `!`)

All require Administrator permissions.

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
| `!shutdown` | stop bot |
| `!help` | list commands |
