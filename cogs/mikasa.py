"""Mikasa Ackerman-specific commands, ship command, and ban protection."""
import discord
from discord.ext import commands
from discord import app_commands
from utils.gifs import get_gif
from utils.game_state import GameState, RANKS
import hashlib
import random

# ── Protected user: Mikasa Ackerman (cannot be banned) ────────────────
MIKASA_USER_ID = 1380905001584431256

MIKASA_BAN_RESPONSES = [
    "❤️ **We can't ban Mikasa Ackerman.** She has protected these walls longer than any of us. *Some soldiers are untouchable.*",
    "🧣 You dare try to ban **Mikasa Ackerman**? Levi himself would refuse this order. *Stand down, soldier.*",
    "🦅 This action is **forbidden**. Mikasa Ackerman is under the protection of the Survey Corps. Her scarf stays on.",
    "⚔️ *Tch.* Even I won't touch Mikasa Ackerman. **The ban has been blocked.** Know your place.",
    "📜 The Military Police reviewed this ban request and **denied it**. Mikasa Ackerman is an irreplaceable asset to humanity's survival.",
    "🦅 **Eren wouldn't allow it.** Neither will this server. Mikasa Ackerman stays. Always.",
]


def _stable_hash(a: int, b: int) -> int:
    """
    Returns a stable 1-100 score for two user IDs.
    Uses SHA-256 so it's always positive, consistent across Python versions,
    and produces the same result regardless of argument order.
    """
    key = str(min(a, b)) + ":" + str(max(a, b))
    digest = hashlib.sha256(key.encode()).hexdigest()
    return (int(digest[:8], 16) % 100) + 1  # always 1-100


class Mikasa(commands.Cog):
    """Mikasa Ackerman themed commands, ship command, and ban protection."""

    def __init__(self, bot):
        self.bot = bot

    # ── Ban protection ───────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        """Intercept any ban of the protected Mikasa user and unban immediately."""
        if user.id != MIKASA_USER_ID:
            return
        try:
            await guild.unban(user, reason="🧣 Mikasa Ackerman is protected. Ban overridden by Levi AI.")
        except (discord.Forbidden, discord.HTTPException):
            pass
        # Notify in the first available channel
        channel = next(
            (c for c in guild.text_channels if c.permissions_for(guild.me).send_messages),
            None
        )
        if channel:
            embed = discord.Embed(
                title="⚠️ Ban Overridden — Mikasa Ackerman",
                description=random.choice(MIKASA_BAN_RESPONSES),
                color=discord.Color.from_rgb(200, 30, 30)
            )
            embed.set_footer(text="❤️ The Survey Corps protects its own.")
            await channel.send(embed=embed)

    # Block !ban command for the protected user
    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context):
        if ctx.command and ctx.command.qualified_name == "ban":
            if ctx.args and len(ctx.args) > 1:
                target = ctx.args[1]
                if isinstance(target, (discord.Member, discord.User)) and target.id == MIKASA_USER_ID:
                    await ctx.send(embed=discord.Embed(
                        title="⚠️ Action Forbidden",
                        description=random.choice(MIKASA_BAN_RESPONSES),
                        color=discord.Color.from_rgb(200, 30, 30)
                    ))
                    ctx.command.reset_cooldown(ctx)
                    raise commands.CommandError("Protected user")

    # ── !ship prefix command ─────────────────────────────────────────
    @commands.command(name="ship", aliases=["shipping"])
    async def ship(self, ctx, user1: discord.Member = None, user2: discord.Member = None):
        """
        Ship two members together! Usage: !ship @user1 @user2
        If only one user is mentioned, ships them with you.
        """
        if user1 is None:
            await ctx.send("❌ Usage: `!ship @user1 @user2` or `!ship @user` to ship with yourself!")
            return

        # If only one user given, ship with the command author
        if user2 is None:
            user2 = ctx.author

        # Don't ship a user with themselves
        if user1.id == user2.id:
            await ctx.send(
                embed=discord.Embed(
                    description=f"🤔 {user1.mention} can't be shipped with themselves... or can they? *Narcissism unlocked.*",
                    color=discord.Color.orange()
                )
            )
            return

        score = _stable_hash(user1.id, user2.id)
        # Build ship name: first half of name1 + second half of name2
        n1 = user1.display_name
        n2 = user2.display_name
        ship_name = n1[:max(1, len(n1) // 2)] + n2[max(0, len(n2) // 2):]

        # Progress bar
        filled = score // 10
        bar = "❤️" * filled + "⬜" * (10 - filled)

        if score >= 90:
            verdict = "🔥 SOULMATES! Their bond rivals Eren & Mikasa!"
            color = discord.Color.from_rgb(255, 30, 80)
        elif score >= 75:
            verdict = "❤️ Deeply in love! A bond beyond the walls!"
            color = discord.Color.red()
        elif score >= 55:
            verdict = "🧡 Strong feelings! The Survey Corps approves!"
            color = discord.Color.orange()
        elif score >= 35:
            verdict = "💛 Potential! Like cadets who might fall for each other..."
            color = discord.Color.gold()
        elif score >= 15:
            verdict = "💙 Just friends... for now. The walls are long."
            color = discord.Color.blue()
        else:
            verdict = "🖤 Total strangers. Maybe they've never met beyond the walls."
            color = discord.Color.dark_grey()

        embed = discord.Embed(
            title=f"❤️ Shipping: {user1.display_name} × {user2.display_name}",
            color=color
        )
        embed.add_field(
            name="💖 Ship Name",
            value=f"**{ship_name}**",
            inline=True
        )
        embed.add_field(
            name="💯 Compatibility Score",
            value=f"**{score}/100**",
            inline=True
        )
        embed.add_field(
            name="❤️ Love Meter",
            value=bar,
            inline=False
        )
        embed.add_field(
            name="📜 Verdict",
            value=verdict,
            inline=False
        )
        embed.set_thumbnail(url=user1.display_avatar.url)
        embed.set_image(url=user2.display_avatar.url)
        embed.set_footer(text="⚔️ Wings of Freedom Ship Calculator • " + ctx.guild.name)
        await ctx.send(embed=embed)

    # ── /ship slash command (same logic) ──────────────────────────────
    @app_commands.command(name="ship", description="Ship two members together and see their compatibility! ❤️")
    @app_commands.describe(user1="First person", user2="Second person (default: you)")
    async def ship_slash(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member = None):
        ctx_like = type("FakeCtx", (), {
            "author": interaction.user,
            "guild": interaction.guild,
            "send": interaction.response.send_message,
        })()
        if user2 is None:
            user2 = interaction.user
        if user1.id == user2.id:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"🤔 {user1.mention} can't be shipped with themselves... *Narcissism unlocked.*",
                    color=discord.Color.orange()
                )
            )
            return
        score = _stable_hash(user1.id, user2.id)
        n1, n2 = user1.display_name, user2.display_name
        ship_name = n1[:max(1, len(n1) // 2)] + n2[max(0, len(n2) // 2):]
        filled = score // 10
        bar = "❤️" * filled + "⬜" * (10 - filled)
        if score >= 90:
            verdict, color = "🔥 SOULMATES! Their bond rivals Eren & Mikasa!", discord.Color.from_rgb(255, 30, 80)
        elif score >= 75:
            verdict, color = "❤️ Deeply in love! A bond beyond the walls!", discord.Color.red()
        elif score >= 55:
            verdict, color = "🧡 Strong feelings! The Survey Corps approves!", discord.Color.orange()
        elif score >= 35:
            verdict, color = "💛 Potential! Like cadets who might fall for each other...", discord.Color.gold()
        elif score >= 15:
            verdict, color = "💙 Just friends... for now.", discord.Color.blue()
        else:
            verdict, color = "🖤 Total strangers. Maybe they've never met beyond the walls.", discord.Color.dark_grey()
        embed = discord.Embed(title=f"❤️ Shipping: {user1.display_name} × {user2.display_name}", color=color)
        embed.add_field(name="💖 Ship Name", value=f"**{ship_name}**", inline=True)
        embed.add_field(name="💯 Score", value=f"**{score}/100**", inline=True)
        embed.add_field(name="❤️ Love Meter", value=bar, inline=False)
        embed.add_field(name="📜 Verdict", value=verdict, inline=False)
        embed.set_thumbnail(url=user1.display_avatar.url)
        embed.set_image(url=user2.display_avatar.url)
        embed.set_footer(text="⚔️ Wings of Freedom Ship Calculator")
        await interaction.response.send_message(embed=embed)

    # ── /ackerman_bond (fixed) ────────────────────────────────────────────
    @app_commands.command(name="ackerman_bond", description="See your Ackerman-style bond with another user")
    async def ackerman_bond(self, interaction: discord.Interaction, user: discord.Member):
        """Calculate an Ackerman bond score — always 1-100, consistent, never breaks."""
        author = interaction.user
        # Use SHA-256 stable hash — always 1-100, never negative
        combined = _stable_hash(author.id, user.id)

        if combined >= 90:
            rating = "🔥 Soulmates! Eternal Devotion! 🔥"
            color = discord.Color.red()
        elif combined >= 75:
            rating = "❤️ Unbreakable Bond! Like family! ❤️"
            color = discord.Color.dark_red()
        elif combined >= 50:
            rating = "🛡️ Strong Protection! Trusted ally! 🛡️"
            color = discord.Color.orange()
        elif combined >= 25:
            rating = "🧩 Fellow Soldier! Reliable companion! 🧩"
            color = discord.Color.blue()
        else:
            rating = "📦 Acquaintance! Room to grow! 📦"
            color = discord.Color.grey()

        prot_filled = combined // 20
        dev_filled = combined // 25

        embed = discord.Embed(
            title=f"🧩 Ackerman Bond: {author.display_name} & {user.display_name}",
            description=f"**Bond Strength:** {combined}/100\n\n{rating}",
            color=color
        )
        embed.add_field(
            name="🛡️ Protection Level",
            value="🔥" * prot_filled + "⬜" * (5 - prot_filled),
            inline=True
        )
        embed.add_field(
            name="❤️ Devotion",
            value="❤️" * dev_filled + "⬜" * (4 - dev_filled),
            inline=True
        )
        embed.set_thumbnail(url=author.display_avatar.url)
        embed.set_footer(text="Eren… for all these years, I’ve liked you.")
        await interaction.response.send_message(embed=embed)

    # ── /mikasa slash command ───────────────────────────────────────────
    @app_commands.command(name="mikasa", description="Mikasa Ackerman themed interactions")
    @app_commands.describe(action="Action to perform", target="Optional target user")
    @app_commands.choices(action=[
        app_commands.Choice(name="red_scarf", value="red_scarf"),
        app_commands.Choice(name="protect", value="protect"),
        app_commands.Choice(name="devotion", value="devotion"),
        app_commands.Choice(name="ackerman_power", value="ackerman_power"),
        app_commands.Choice(name="salute", value="salute"),
    ])
    async def mikasa(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        target: discord.Member = None
    ):
        author = interaction.user
        target_name = target.display_name if target else "everyone"
        mikasa_actions = {
            "red_scarf": {
                "emoji": "🧣",
                "color": discord.Color.red(),
                "template": "{author} wraps the red scarf around {target} — keeping them safe!",
                "query": "mikasa red scarf anime",
                "fallback": "mikasa_red_scarf"
            },
            "protect": {
                "emoji": "🛡️",
                "color": discord.Color.dark_red(),
                "template": "{author} protects {target} with Mikasa's fierce devotion!",
                "query": "mikasa protect anime",
                "fallback": "mikasa_protect"
            },
            "devotion": {
                "emoji": "❤️",
                "color": discord.Color.dark_red(),
                "template": "{author} shows absolute devotion to {target} like Mikasa would!",
                "query": "mikasa devotion anime",
                "fallback": "mikasa_eren"
            },
            "ackerman_power": {
                "emoji": "🔥",
                "color": discord.Color.orange(),
                "template": "{author} awakens their Ackerman power before {target}! 🔥",
                "query": "mikasa ackerman power",
                "fallback": "mikasa_power"
            },
            "salute": {
                "emoji": "🧩",
                "color": discord.Color(0x5B83D5),
                "template": "{author} and {target} salute together — Wings of Freedom! 🧩",
                "query": "survey corps salute",
                "fallback": "mikasa_salute"
            },
        }
        act = mikasa_actions[action.value]
        gif_url = await get_gif(act["fallback"], act["query"])
        desc = act["template"].format(author=author.display_name, target=target_name)
        embed = discord.Embed(
            title=f"{act['emoji']} Mikasa's {action.value.replace('_', ' ').title()}",
            description=f"**{desc}**",
            color=act["color"]
        )
        if gif_url:
            embed.set_image(url=gif_url)
        embed.set_footer(text="🧩 A Wings of Freedom | Requested by " + author.display_name)
        await interaction.response.send_message(embed=embed)

    # ── /mikasa_stats ─────────────────────────────────────────────────
    @app_commands.command(name="mikasa_stats", description="View Mikasa Ackerman's combat statistics")
    async def mikasa_stats(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚔️ Mikasa Ackerman - Combat Profile",
            description="**Humanity's Strongest Soldier (Alongside Levi)**",
            color=discord.Color.dark_red()
        )
        embed.add_field(name="Affiliation", value="Survey Corps - Special Operations Squad", inline=True)
        embed.add_field(name="Age", value="19 (Final Season)", inline=True)
        embed.add_field(name="Height", value="170 cm", inline=True)
        embed.add_field(name="Rank", value="Officer - Top 10 Graduate", inline=True)
        embed.add_field(name="Titan Power", value="Inheritor of War Hammer Titan (briefly)", inline=False)
        embed.add_field(name="Combat Stats", value="🔥 **Speed:** SSS | ⚔️ **Skill:** SSS | 🛡️ **Defense:** SS | 💥 **Power:** SS", inline=False)
        embed.add_field(name="Specialties", value="Blade Mastery • Ackerman Power • Tactical Genius • Titan Slaying", inline=False)
        embed.add_field(name="Kills (Estimated)", value="100+ Titans", inline=True)
        embed.add_field(name="Status", value="Active - Protecting Paradis", inline=True)
        embed.set_thumbnail(url="https://static.wikia.nocookie.net/shingekinokyojin/images/3/37/Mikasa_Ackerman.png/revision/latest/scale-to-width-down/400")
        embed.set_footer(text="🧩 Wings of Freedom | Eren… I’ve always been with you.")
        await interaction.response.send_message(embed=embed)

    # ── Prefix commands ─────────────────────────────────────────────────
    @commands.command(name="mikasa")
    async def mikasa_react(self, ctx, member: discord.Member = None):
        target = member.display_name if member else "everyone"
        gif_url = await get_gif("mikasa_protect", "mikasa protect anime")
        embed = discord.Embed(
            title="⚔️ Mikasa's Protection",
            description=f"**{ctx.author.display_name} protects {target} with Mikasa's devotion! ⚔️**",
            color=discord.Color.dark_red()
        )
        if gif_url:
            embed.set_image(url=gif_url)
        embed.set_footer(text="🧩 A Wings of Freedom")
        await ctx.send(embed=embed)

    @commands.command(name="red_scarf")
    async def red_scarf(self, ctx, member: discord.Member = None):
        target = member.display_name if member else "everyone"
        gif_url = await get_gif("mikasa_scarf", "mikasa red scarf anime")
        embed = discord.Embed(
            title="🧣 Red Scarf of Devotion",
            description=f"**{ctx.author.display_name} wraps the red scarf around {target}**, keeping them safe 🧣",
            color=discord.Color.red()
        )
        if gif_url:
            embed.set_image(url=gif_url)
        embed.set_footer(text="❤️ I want to be with you… always.")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Mikasa(bot))
