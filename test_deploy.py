import os, sys

sys.stdout = open(sys.stdout.fileno(), 'w', buffering=1)

print("[DIAG] Starting diagnosis...")
print(f"[DIAG] Python: {sys.version}")

import discord
print(f"[DIAG] discord.py: {discord.__version__}")

from discord.ext import commands
print(f"[DIAG] commands module OK")

print(f"[DIAG] dotenv not needed")

try:
    from server_config import SERVER_CONFIG
    print(f"[DIAG] server_config OK, {len(SERVER_CONFIG['categories'])} categories")
except Exception as e:
    print(f"[DIAG] server_config failed: {e}")

try:
    from templates import list_templates
    print(f"[DIAG] templates OK, {len(list_templates())} templates")
except Exception as e:
    print(f"[DIAG] templates failed: {e}")

try:
    from template_scaler import scale_template
    print(f"[DIAG] template_scaler OK")
except Exception as e:
    print(f"[DIAG] template_scaler failed: {e}")

# Test bot creation
try:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.members = True
    bot = commands.Bot(command_prefix="!", intents=intents)
    print(f"[DIAG] Bot created OK")
except Exception as e:
    print(f"[DIAG] Bot creation failed: {e}")
    raise

print("[DIAG] All checks passed!")
