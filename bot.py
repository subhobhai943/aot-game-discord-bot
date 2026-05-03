import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from cogs.settings import get_prefix

load_dotenv()


def get_prefix_for_bot(bot, message):
    """Dynamic prefix per server.
    Returns BOTH 'aot help' (with space) AND 'aothelp' (no space) so either works.
    """
    if message.guild:
        p = get_prefix(message.guild.id)
        return [p + " ", p]   # try 'aot help' first, then 'aothelp'
    return ["! ", "!"]


intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Required for AFK nickname changes and member monitoring

bot = commands.Bot(command_prefix=get_prefix_for_bot, intents=intents)

COGS = [
    "cogs.settings",
    "cogs.help",
    "cogs.battle",
    "cogs.lore",
    "cogs.odm",
    "cogs.profile",
    "cogs.arena",
    "cogs.gifs",      # OwO-style AoT reaction GIF commands
    "cogs.mikasa",    # Mikasa Ackerman specific features
    "cogs.games",     # Trivia, titan spawn, ODM training games
    "cogs.abilities", # Character abilities and titan transformations
    "cogs.afk",       # AoT-themed AFK system
    "cogs.automod",   # OpenRouter Gemma-4 AI auto-moderation
    "cogs.music",     # Music player — YouTube, Spotify search, ping
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
