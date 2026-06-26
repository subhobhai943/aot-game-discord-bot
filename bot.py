"""ODM Striker — AoT Discord game bot."""
import os
import asyncio
import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv
import utils.gifs as gifs_module

load_dotenv()

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True
INTENTS.reactions = True

DEFAULT_PREFIX = ">"

import cogs.settings


def get_prefix(bot, message):
    """Return the custom prefix for the guild, falling back to DEFAULT_PREFIX."""
    p = DEFAULT_PREFIX
    if message.guild:
        guild_p = cogs.settings.get_prefix(message.guild.id)
        # get_prefix returns '!' when no custom prefix is set; treat that as
        # "not configured" and fall back to DEFAULT_PREFIX.
        if guild_p != "!":
            p = guild_p

    prefixes = [p]
    # Also accept the prefix followed by a space
    if not p.endswith(" "):
        prefixes.append(f"{p} ")

    # Longer prefixes must come first so discord.py matches them greedily
    prefixes.sort(key=len, reverse=True)
    return commands.when_mentioned_or(*prefixes)(bot, message)


COGS = [
    "cogs.settings",
    "cogs.help",
    "cogs.battle",
    "cogs.lore",
    "cogs.odm",
    "cogs.profile",
    "cogs.arena",
    "cogs.gifs",
    "cogs.mikasa",
    "cogs.games",
    "cogs.abilities",
    "cogs.afk",
    "cogs.automod",
    "cogs.music",
    "cogs.colors",
    "cogs.lookup",
    "cogs.activate_rumbling",
    "cogs.titan_catch",
    "cogs.pvp",
    "cogs.leaderboard",
    "cogs.titan_game",
    "cogs.among_titans",
    "cogs.shop",
    "cogs.raid",
    "cogs.utility",
    "cogs.laboratory",
    "cogs.snipe",
    "cogs.squad",
    "cogs.regiments",
    "cogs.games3d",
    "cogs.platformer",
]


class AoTBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=get_prefix,
            intents=INTENTS,
            help_command=None,
            case_insensitive=True,
        )
        self.http_session: aiohttp.ClientSession | None = None

    async def setup_hook(self):
        # Initialize SQLite database helper
        from utils.db import Database
        await Database.init()

        self.http_session = aiohttp.ClientSession()
        gifs_module.SESSION = self.http_session

        loaded, failed = [], []
        for cog in COGS:
            try:
                await self.load_extension(cog)
                loaded.append(cog)
            except Exception as e:
                failed.append((cog, e))

        for name in loaded:
            print(f"  [OK] Loaded {name}")
        for name, err in failed:
            print(f"  [FAIL] Failed to load {name}: {err}")

        try:
            synced = await self.tree.sync()
            print(f"  [OK] All slash commands synced! ({len(synced)} commands)")
        except Exception as e:
            print(f"  [FAIL] Slash sync failed: {e}")

    async def close(self):
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
        await super().close()

    async def on_ready(self):
        print(f"\n{'='*50}")
        print(f"  ODM Striker is online!")
        print(f"  Logged in as: {self.user} (ID: {self.user.id})")
        print(f"  Guilds: {len(self.guilds)}")
        print(f"{'='*50}\n")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="The Rumbling | >help"
            )
        )

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(f"❌ You do not have permission to use this command. Required: `{', '.join(error.missing_permissions)}`.")
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing argument: `{error.param.name}`")
            return
        if isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Invalid argument provided. Please check the command usage.")
            return
        logging.error(f"Command error in {ctx.command}: {error}", exc_info=error)
        await ctx.send(f"❌ An error occurred while executing the command.")


def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN not set in .env")
    bot = AoTBot()
    asyncio.run(bot.start(token))


if __name__ == "__main__":
    main()
