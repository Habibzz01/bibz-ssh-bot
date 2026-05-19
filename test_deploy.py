import os, sys, traceback

print("[TEST] Starting...", flush=True)
print(f"[TEST] Python: {sys.version}", flush=True)
print(f"[TEST] TOKEN: {'yes' if os.getenv('DISCORD_BOT_TOKEN') else 'no'}", flush=True)

try:
    import discord
    print(f"[TEST] discord.py v{discord.__version__}", flush=True)
    from discord.ext import commands
    from dotenv import load_dotenv
    from templates import get_template, list_templates
    print(f"[TEST] Templates: {len(list_templates())}", flush=True)
    
    import server_config
    from template_scaler import scale_template
    from template_utils import format_template_preview, format_template_diff
    print("[TEST] All imports OK", flush=True)
    
    token = os.getenv("DISCORD_BOT_TOKEN")
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.members = True
    bot = commands.Bot(command_prefix="!", intents=intents)
    
    @bot.event
    async def on_ready():
        print(f"[BOT] Connected as {bot.user}", flush=True)
        print(f"[BOT] Guilds: {len(bot.guilds)}", flush=True)
    
    print("[TEST] Calling bot.run()...", flush=True)
    bot.run(token)
    
except Exception as e:
    print(f"[CRASH] {type(e).__name__}: {e}", flush=True)
    traceback.print_exc(file=sys.stdout, flush=True)
    sys.exit(1)
