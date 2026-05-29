"""Auto-purge for the color-role channel.

Deletes ALL messages (including bot responses & slash command invocations)
from COLOR_CHANNEL_ID after AUTO_DELETE_DELAY seconds.

Works by:
1. on_message        — catches normal text messages in the channel
2. on_interaction    — catches slash command uses; after the interaction
                       is done we fetch & delete both the invocation
                       marker and the bot follow-up reply
3. A background task that purges the whole channel every minute as a
   safety net for any messages that slipped through.
"""
import asyncio
import discord
from discord.ext import commands, tasks

# ── Config ──────────────────────────────────────────────────────────
COLOR_CHANNEL_ID: int = 1478258000580837469
AUTO_DELETE_DELAY: int = 5   # seconds after which individual messages are deleted
PURGE_INTERVAL:   int = 1    # minutes between full-channel safety purges


class ColorChannelPurge(commands.Cog):
    """Keeps the color-role channel clean by deleting every message."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.periodic_purge.start()

    def cog_unload(self) -> None:
        self.periodic_purge.cancel()

    # ── Helper ──────────────────────────────────────────────────────────
    async def _delete_after(self, message: discord.Message) -> None:
        """Wait AUTO_DELETE_DELAY seconds then delete the message."""
        await asyncio.sleep(AUTO_DELETE_DELAY)
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    # ── Listener 1: normal messages ───────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.channel.id != COLOR_CHANNEL_ID:
            return
        asyncio.create_task(self._delete_after(message))

    # ── Listener 2: slash command interactions (set color / remove color) ─────
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction) -> None:
        """Fires when any slash command is used anywhere.
        We filter to our channel only and delete the response after a delay.
        """
        if not interaction.channel:
            return
        if interaction.channel.id != COLOR_CHANNEL_ID:
            return
        if interaction.type != discord.InteractionType.application_command:
            return

        # Wait for the external bot to finish sending its reply, then purge
        await asyncio.sleep(AUTO_DELETE_DELAY + 2)  # +2 s buffer for bot reply
        try:
            # Bulk-delete the last 10 messages — catches both the
            # "OBITO used set color" line AND the COLOR TITAN reply embed
            channel = interaction.channel
            messages = [m async for m in channel.history(limit=10)]
            await channel.delete_messages(messages)
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ── Background task: full purge every PURGE_INTERVAL minutes ───────────
    @tasks.loop(minutes=PURGE_INTERVAL)
    async def periodic_purge(self) -> None:
        """Safety net: wipe the whole channel every minute."""
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(COLOR_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            await channel.purge(limit=100)
        except (discord.Forbidden, discord.HTTPException):
            pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ColorChannelPurge(bot))
