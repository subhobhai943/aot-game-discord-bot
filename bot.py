import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from cogs.settings import get_prefix

load_dotenv()


def get_prefix_for_bot(bot, message):
    """Dynamic prefix per server."""
    if message.guild:
        return get_prefix(message.guild.id)
    return "!"


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=get_prefix_for_bot, intents=intents)

COGS = [
    "cogs.settings",
    "cogs.help",
    "cogs.battle",
    "cogs.lore",
    "cogs.odm",
    "cogs.profile",
    "cogs.arena",
]


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"  ✔ Loaded {cog}")
        except Exception as e:
            print(f"  ❌ Failed to load {cog}: {e}")
    await bot.tree.sync()
    print("✅ All slash commands synced!")


bot.run(os.getenv("DISCORD_TOKEN"))
