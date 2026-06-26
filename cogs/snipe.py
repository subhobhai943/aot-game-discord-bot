"""Snipe Cog: Tracks and displays the last 10 deleted messages in each channel."""
from __future__ import annotations
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional


class Snipe(commands.Cog):
    """🎯 Snipe system: recover recently deleted messages."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Map channel_id (int) -> list of dict (max 10 items)
        self.snipe_cache: dict[int, list[dict]] = {}

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return  # Ignore bots and DMs

        channel_id = message.channel.id
        if channel_id not in self.snipe_cache:
            self.snipe_cache[channel_id] = []

        self.snipe_cache[channel_id].insert(0, {
            "author_name": message.author.display_name,
            "author_avatar": message.author.display_avatar.url,
            "author_mention": message.author.mention,
            "content": message.content or "*[Empty or Embed/Attachment only]*",
            "attachments": [a.url for a in message.attachments],
            "timestamp": message.created_at
        })

        # Limit to last 10
        self.snipe_cache[channel_id] = self.snipe_cache[channel_id][:10]

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: list[discord.Message]):
        for message in reversed(messages):
            if message.author.bot or not message.guild:
                continue

            channel_id = message.channel.id
            if channel_id not in self.snipe_cache:
                self.snipe_cache[channel_id] = []

            self.snipe_cache[channel_id].insert(0, {
                "author_name": message.author.display_name,
                "author_avatar": message.author.display_avatar.url,
                "author_mention": message.author.mention,
                "content": message.content or "*[Empty or Embed/Attachment only]*",
                "attachments": [a.url for a in message.attachments],
                "timestamp": message.created_at
            })
            self.snipe_cache[channel_id] = self.snipe_cache[channel_id][:10]

    # ── Snipe command ────────────────────────────────────────────────────────
    def _build_snipe_embed(self, channel_id: int, index: int, requester_name: str) -> tuple[Optional[discord.Embed], Optional[str]]:
        history = self.snipe_cache.get(channel_id, [])
        if not history:
            return None, "❌ No recently deleted messages found in this channel."

        if index < 1 or index > len(history):
            return None, f"❌ Invalid index. Please choose a number between `1` and `{len(history)}` (1 is the most recent)."

        msg = history[index - 1]
        embed = discord.Embed(
            title=f"🎯 Sniped Message #{index}",
            description=msg["content"],
            color=0xE74C3C
        )
        embed.set_author(name=msg["author_name"], icon_url=msg["author_avatar"])
        embed.add_field(name="Author", value=msg["author_mention"], inline=True)
        embed.add_field(name="Sent At", value=discord.utils.format_dt(msg["timestamp"], 't'), inline=True)
        
        if msg["attachments"]:
            att_list = "\n".join([f"🔗 [Attachment {i+1}]({url})" for i, url in enumerate(msg["attachments"])])
            embed.add_field(name="Attachments", value=att_list, inline=False)
            # Try to show first image if it is one
            first = msg["attachments"][0]
            if any(ext in first.lower() for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]):
                embed.set_image(url=first)

        embed.set_footer(text=f"Sniped by {requester_name} | {index}/{len(history)} in history")
        return embed, None

    @commands.command(name="snipe", help="Retrieve the last deleted message. Use prefix and index (1-10) to see older ones (e.g. >snipe 3).")
    @commands.guild_only()
    async def snipe_prefix(self, ctx: commands.Context, index: int = 1):
        embed, err = self._build_snipe_embed(ctx.channel.id, index, ctx.author.display_name)
        if err:
            await ctx.send(err)
        else:
            await ctx.send(embed=embed)

    @app_commands.command(name="snipe", description="Retrieve recently deleted messages in this channel")
    @app_commands.guild_only()
    @app_commands.describe(index="Message position (1 = most recent, max 10)")
    async def snipe_slash(self, interaction: discord.Interaction, index: int = 1):
        embed, err = self._build_snipe_embed(interaction.channel_id, index, interaction.user.display_name)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed)

    # ── Snipelist command ────────────────────────────────────────────────────
    def _build_snipelist_embed(self, channel_id: int) -> tuple[Optional[discord.Embed], Optional[str]]:
        history = self.snipe_cache.get(channel_id, [])
        if not history:
            return None, "❌ No recently deleted messages found in this channel."

        embed = discord.Embed(
            title="🎯 Snipe History (Last 10 Deleted Messages)",
            description="Use `/snipe <index>` or `>snipe <index>` to view the full content of any message.\n\n",
            color=0xE74C3C
        )

        lines = []
        for idx, msg in enumerate(history):
            content_preview = msg["content"][:40] + "..." if len(msg["content"]) > 40 else msg["content"]
            time_str = discord.utils.format_dt(msg["timestamp"], 't')
            attachments_marker = " 📎" if msg["attachments"] else ""
            lines.append(f"`{idx + 1}.` {msg['author_mention']}: {content_preview}{attachments_marker} *({time_str})*")

        embed.description += "\n".join(lines)
        embed.set_footer(text=f"Total cached: {len(history)}/10")
        return embed, None

    @commands.command(name="snipelist", aliases=["sl"], help="List the last 10 deleted messages in this channel.")
    @commands.guild_only()
    async def snipelist_prefix(self, ctx: commands.Context):
        embed, err = self._build_snipelist_embed(ctx.channel.id)
        if err:
            await ctx.send(err)
        else:
            await ctx.send(embed=embed)

    @app_commands.command(name="snipelist", description="List the last 10 deleted messages in this channel")
    @app_commands.guild_only()
    async def snipelist_slash(self, interaction: discord.Interaction):
        embed, err = self._build_snipelist_embed(interaction.channel_id)
        if err:
            await interaction.response.send_message(err, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Snipe(bot))
