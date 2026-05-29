"""Auto-purge for the color-role channel.

Any message sent in COLOR_CHANNEL_ID is automatically deleted after
AUTO_DELETE_DELAY seconds. This keeps the channel clean after users
pick their colour from the COLOR TITAN bot.
"""
import asyncio
import discord
from discord.ext import commands

# ── Config ──────────────────────────────────────────────────────────────────
COLOR_CHANNEL_ID: int = 1478258000580837469   # #color-role channel
AUTO_DELETE_DELAY: int = 5                    # seconds before deletion


class ColorChannelPurge(commands.Cog):
    """Watches the color-role channel and deletes every message after a delay."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Delete any message in the color channel after AUTO_DELETE_DELAY seconds."""
        if message.channel.id != COLOR_CHANNEL_ID:
            return  # Not our channel — ignore

        await asyncio.sleep(AUTO_DELETE_DELAY)
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass  # Already deleted or no permission — silently skip

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        """Also delete edited messages in the color channel (e.g. bot embed updates)."""
        if after.channel.id != COLOR_CHANNEL_ID:
            return

        await asyncio.sleep(AUTO_DELETE_DELAY)
        try:
            await after.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ColorChannelPurge(bot))
