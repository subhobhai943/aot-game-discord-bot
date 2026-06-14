"""Placeholder cog — intentionally empty.

OwO-style mini-games were removed. To add new games, create a
dedicated cog file with unique command names instead of adding here.
"""
from discord.ext import commands


class OwoGames(commands.Cog):
    """Empty placeholder — not loaded by the bot."""


async def setup(bot: commands.Bot) -> None:  # noqa: D401
    """No-op setup — cog not registered."""
