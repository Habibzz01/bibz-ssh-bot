import nextcord
from nextcord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_BOT_TOKEN")

if not TOKEN:
    print("❌ Token tidak ditemukan. Cek file .env")
    exit(1)

intents = nextcord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot {bot.user} siap!")
    print("Ketik !setup_server di server Discord.")

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_server(ctx):
    guild = ctx.guild
    template = {
        "📢ㅤANNOUNCEMENT": ["📢ㅤannouncement", "📜ㅤrules"],
        "💬ㅤGENERAL": ["💬ㅤgeneral-chat", "📊ㅤreport-bug"],
        "🔐ㅤSSHㅤACCOUNT": ["🆓ㅤfree-account", "👑ㅤpremium-zone"],
        "⚙️ㅤSUPPORT": ["❓ㅤsupport-ticket", "📌ㅤfaq"],
        "📡ㅤLIVEㅤTUNNEL": ["📡ㅤlive-test", "📁ㅤconfig-share"]
    }
    await ctx.send("🚀 Membuat struktur server...")
    for cat_name, channels in template.items():
        category = await guild.create_category(cat_name)
        for ch_name in channels:
            await guild.create_text_channel(ch_name, category=category)
    await ctx.send("✅ Struktur server BIBZ SSH berhasil dibuat!")

bot.run(TOKEN)
