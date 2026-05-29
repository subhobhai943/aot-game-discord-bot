"""Auto-purge for the color-role channel.

Deletes messages in COLOR_CHANNEL_ID after AUTO_DELETE_DELAY seconds.
PINNED messages (the color guide) are NEVER deleted.
"""
import asyncio
import discord
from discord.ext import commands, tasks

# ── Config ──────────────────────────────────────────────────────────
COLOR_CHANNEL_ID: int = 1478258000580837469
AUTO_DELETE_DELAY: int = 5   # seconds before individual messages are deleted
PURGE_INTERVAL:   int = 1    # minutes between full-channel safety purges


class ColorChannelPurge(commands.Cog):
    """Keeps the color-role channel clean; never touches pinned messages."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.periodic_purge.start()

    def cog_unload(self) -> None:
        self.periodic_purge.cancel()

    # ── Helper: safe single-message delete ─────────────────────────────
    async def _delete_after(self, message: discord.Message) -> None:
        """Wait then delete — but NEVER delete pinned messages."""
        await asyncio.sleep(AUTO_DELETE_DELAY)
        try:
            # Re-fetch to get the latest pinned state
            msg = await message.channel.fetch_message(message.id)
            if msg.pinned:
                return  # ⬅ Skip the color guide
            await msg.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    # ── Listener 1: normal/bot messages ────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.channel.id != COLOR_CHANNEL_ID:
            return
        asyncio.create_task(self._delete_after(message))

    # ── Listener 2: slash command interactions ─────────────────────────
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        if not interaction.channel:
            return
        if interaction.channel.id != COLOR_CHANNEL_ID:
            return
        if interaction.type != discord.InteractionType.application_command:
            return

        # Wait for COLOR TITAN to send its reply
        await asyncio.sleep(AUTO_DELETE_DELAY + 2)
        try:
            channel = interaction.channel
            # Fetch pinned message IDs so we never touch them
            pinned_ids = {m.id for m in await channel.pins()}
            messages = [
                m async for m in channel.history(limit=10)
                if m.id not in pinned_ids   # ⬅ skip pinned guide
            ]
            if messages:
                await channel.delete_messages(messages)
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ── Background task: safety purge every PURGE_INTERVAL minutes ────────
    @tasks.loop(minutes=PURGE_INTERVAL)
    async def periodic_purge(self) -> None:
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(COLOR_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            pinned_ids = {m.id for m in await channel.pins()}
            # purge() accepts a check function — skip pinned messages
            await channel.purge(
                limit=100,
                check=lambda m: m.id not in pinned_ids  # ⬅ never delete guide
            )
        except (discord.Forbidden, discord.HTTPException):
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ColorChannelPurge(bot))
