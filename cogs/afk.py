import discord
from discord.ext import commands
from discord import app_commands
import datetime

# In-memory AFK store: {user_id: {"reason": str, "since": datetime}}
afk_users: dict[int, dict] = {}

# Tracks message IDs that SET afk, so on_message doesn't immediately clear it
_afk_set_by_message: set[int] = set()

AOT_AFK_QUOTES = [
    "🗡️ **{user}** has left for the battlefield... *Beyond the walls.*",
    "🌊 **{user}** has retreated like the ocean — *The sea beyond the walls calls.*",
    "⚔️ **{user}** is resting in Trost. *A soldier must recover to fight again.*",
    "🏰 **{user}** has withdrawn behind Wall Maria. *The Survey Corps needs time.*",
    "🦅 **{user}** soared away on ODM gear. *See you when they return.*",
    "🌙 **{user}** is dreaming of freedom beyond the walls...",
    "🪖 **{user}** has gone to resupply at the supply depot.",
    "🌿 **{user}** has ventured beyond Wall Rose into the unknown.",
]

AOT_BACK_QUOTES = [
    "⚔️ **{user}** has returned from beyond the walls! *Ready to fight.*",
    "🗡️ **{user}** charges back into battle! *The Titan Shifter awakens!*",
    "🏰 **{user}** has reclaimed their post! *Welcome back, soldier.*",
    "🦅 **{user}** swooped back in on ODM gear! *The Scout is back.*",
    "🙌 **{user}** emerges from the shadows, ready for duty!",
]

# Stable AoT-themed thumbnail (Wings of Freedom style, no imgur)
AOT_THUMBNAIL = "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Single_apple.png/240px-Single_apple.png"
# Use the bot's own avatar as fallback — set in _set_afk at runtime


def _fmt_duration(duration: datetime.timedelta) -> str:
    """Format a timedelta into a human-readable string like '2h 5m 30s'."""
    total = max(0, int(duration.total_seconds()))
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


class AFK(commands.Cog):
    """AoT-themed AFK system — let soldiers rest beyond the walls."""

    def __init__(self, bot):
        self.bot = bot

    # ── Prefix command ─────────────────────────────────────────────────
    @commands.command(name="afk", aliases=["AFK"])
    async def afk_prefix(self, ctx, *, reason: str = "Gone beyond the walls"):
        """Set yourself as AFK with an AoT-themed message."""
        # Mark this message so on_message doesn't immediately unset AFK
        _afk_set_by_message.add(ctx.message.id)
        await self._set_afk(ctx.author, reason, ctx)

    # ── Slash command ───────────────────────────────────────────────────
    @app_commands.command(name="afk", description="Go AFK with an AoT-themed message 🗡️")
    @app_commands.describe(reason="Why are you going AFK? (default: Gone beyond the walls)")
    async def afk_slash(self, interaction: discord.Interaction, reason: str = "Gone beyond the walls"):
        # Slash commands don't fire on_message so no guard needed
        await self._set_afk(interaction.user, reason, interaction)

    # ── Shared helper ───────────────────────────────────────────────────
    async def _set_afk(self, user: discord.Member, reason: str, ctx_or_interaction):
        import random
        now = datetime.datetime.utcnow()
        afk_users[user.id] = {"reason": reason, "since": now}

        quote = random.choice(AOT_AFK_QUOTES).format(user=user.display_name)

        embed = discord.Embed(
            title="🗡️ Soldier Has Left The Walls",
            description=quote,
            color=discord.Color.from_rgb(180, 40, 40)  # AoT dark red
        )
        embed.add_field(name="📜 Reason", value=reason, inline=False)
        embed.add_field(
            name="⏰ Departed",
            value=f"<t:{int(now.timestamp())}:R>",
            inline=True
        )
        embed.set_footer(text="The Survey Corps will remember you, soldier. ⚔️")

        # Use the user's own avatar as thumbnail — always works, no broken URLs
        avatar_url = user.display_avatar.url
        embed.set_thumbnail(url=avatar_url)

        # Try to set [AFK] nickname
        try:
            await user.edit(nick=f"[AFK] {user.display_name}"[:32])
        except (discord.Forbidden, discord.HTTPException):
            pass

        if isinstance(ctx_or_interaction, discord.Interaction):
            await ctx_or_interaction.response.send_message(embed=embed)
        else:
            await ctx_or_interaction.send(embed=embed)

    # ── Listen for messages to unset AFK / notify AFK pings ──────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        import random

        # ── Return from AFK ───────────────────────────────────────
        if message.author.id in afk_users:
            # Skip the exact message that triggered the !afk command
            if message.id in _afk_set_by_message:
                _afk_set_by_message.discard(message.id)
                return

            data = afk_users.pop(message.author.id)
            since: datetime.datetime = data["since"]
            duration = datetime.datetime.utcnow() - since
            time_str = _fmt_duration(duration)

            back_quote = random.choice(AOT_BACK_QUOTES).format(user=message.author.display_name)
            embed = discord.Embed(
                title="⚔️ Soldier Has Returned!",
                description=back_quote,
                color=discord.Color.from_rgb(40, 160, 80)  # AoT green
            )
            embed.add_field(name="🕰️ Time Away", value=time_str, inline=True)
            embed.add_field(name="📜 Was Away For", value=data["reason"], inline=True)
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.set_footer(text="Back on duty, soldier! ⚔️")

            # Remove [AFK] from nickname
            try:
                nick = message.author.display_name
                if nick.startswith("[AFK] "):
                    nick = nick[6:]
                # Restore original nick (set to None if same as username)
                await message.author.edit(
                    nick=None if nick == message.author.name else nick[:32]
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

            await message.channel.send(embed=embed, delete_after=12)

        # ── Notify if user pinged an AFK member ──────────────────────
        for mentioned in message.mentions:
            if mentioned.id in afk_users and mentioned.id != message.author.id:
                data = afk_users[mentioned.id]
                embed = discord.Embed(
                    title="🔕 That Soldier Is AFK!",
                    description=f"⚔️ **{mentioned.display_name}** is currently beyond the walls...",
                    color=discord.Color.dark_gold()
                )
                embed.add_field(name="📜 Reason", value=data["reason"], inline=False)
                embed.add_field(
                    name="⏰ AFK Since",
                    value=f"<t:{int(data['since'].timestamp())}:R>",
                    inline=True
                )
                embed.set_thumbnail(url=mentioned.display_avatar.url)
                embed.set_footer(text="🗡️ They will return when the time is right.")
                await message.channel.send(embed=embed, delete_after=8)

    # ── List all AFK members in this server ──────────────────────────
    @commands.command(name="afklist", aliases=["afk_list"])
    async def afk_list(self, ctx):
        """List all currently AFK soldiers in this server."""
        guild_afk = [
            (uid, data) for uid, data in afk_users.items()
            if ctx.guild.get_member(uid) is not None
        ]
        if not guild_afk:
            embed = discord.Embed(
                title="⚔️ All Soldiers Are On Duty!",
                description="No members are currently AFK. *The walls are defended.*",
                color=discord.Color.green()
            )
            return await ctx.send(embed=embed)

        embed = discord.Embed(
            title="🏰 Soldiers Beyond The Walls",
            color=discord.Color.dark_red()
        )
        for uid, data in guild_afk:
            member = ctx.guild.get_member(uid)
            embed.add_field(
                name=f"🗡️ {member.display_name}",
                value=(
                    f"**Reason:** {data['reason']}\n"
                    f"**Since:** <t:{int(data['since'].timestamp())}:R>"
                ),
                inline=False
            )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AFK(bot))
