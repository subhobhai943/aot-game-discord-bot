import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

COGS = [
    "cogs.battle",
    "cogs.lore",
    "cogs.odm",
    "cogs.profile",
    "cogs.arena",
]

@bot.event
async def on_ready():
    print(f"\u2705 Logged in as {bot.user}")
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"  \u2714 Loaded {cog}")
        except Exception as e:
            print(f"  \u274c Failed to load {cog}: {e}")
    await bot.tree.sync()
    print("\u2705 All slash commands synced!")

bot.run(os.getenv("DISCORD_TOKEN"))
