"""OwO-style titan spawning, catching, collection, and scouting system.

FIX: Replaced >catch text prompt with a discord.ui.Button.
FIX: Removed all local asset image references — uses external CDN URLs from game_state.TITAN_IMAGES.
"""
from __future__ import annotations
import asyncio
import random
import discord
from discord.ext import commands, tasks
from utils.game_state import (
    GameState, TITAN_STATS, TITAN_IMAGES, TITAN_WEIGHTS,
    RARITY_COLOR, RARITY_EMOJI, SURVEY_CORPS_ICON
)

CATCH_TIMEOUT   = 60   # seconds to catch a spawned titan
SPAWN_INTERVAL  = (120, 300)  # random seconds between auto-spawns

# Tracks the currently active spawn per guild: guild_id -> {titan, message_id, caught}
_active_spawns: dict[int, dict] = {}


def _spawn_weights():
    names   = list(TITAN_WEIGHTS.keys())
    weights = list(TITAN_WEIGHTS.values())
    return random.choices(names, weights=weights, k=1)[0]


def _spawn_embed(titan_name: str) -> discord.Embed:
    stats  = TITAN_STATS[titan_name]
    rarity = stats["rarity"]
    color  = RARITY_COLOR[rarity]
    embed  = discord.Embed(
        title="👹 A Wild Titan Appears!",
        description=(
            f"**{RARITY_EMOJI[rarity]} {titan_name}** has been spotted near the walls!\n"
            f"Click the **Catch!** button below before it escapes!"
        ),
        color=color
    )
    embed.set_image(url=TITAN_IMAGES.get(titan_name, SURVEY_CORPS_ICON))
    embed.add_field(name="⚔️ ATK",    value=stats["atk"], inline=True)
    embed.add_field(name="🛡️ DEF",    value=stats["def"], inline=True)
    embed.add_field(name="💨 SPD",    value=stats["spd"], inline=True)
    embed.add_field(name="❤️ HP",     value=stats["hp"],  inline=True)
    embed.add_field(name="⭐ Rarity", value=f"{RARITY_EMOJI[rarity]} {rarity}", inline=True)
    embed.set_footer(text=f"⏳ You have {CATCH_TIMEOUT}s to catch it!")
    return embed


# ── Catch Button View ─────────────────────────────────────────────────────
class CatchView(discord.ui.View):
    """A View with a single 'Catch!' button that handles the titan catch flow."""

    def __init__(self, guild_id: int, titan_name: str, channel: discord.TextChannel):
        super().__init__(timeout=CATCH_TIMEOUT)
        self.guild_id   = guild_id
        self.titan_name = titan_name
        self.channel    = channel
        self.caught     = False

    @discord.ui.button(label="⚔️ Catch!", style=discord.ButtonStyle.danger, emoji="🗡️")
    async def catch_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        spawn = _active_spawns.get(self.guild_id)
        if not spawn or spawn["caught"]:
            await interaction.response.send_message(
                "❌ This titan was already caught or escaped!", ephemeral=True
            )
            return

        spawn["caught"] = True
        self.caught = True
        _active_spawns.pop(self.guild_id, None)
        self.stop()

        # Disable button on the original message
        button.disabled = True
        button.label = "✅ Caught!"
        button.style = discord.ButtonStyle.success
        await interaction.message.edit(view=self)

        player = GameState.get_player(str(interaction.user.id), interaction.user.display_name)
        player.add_titan(self.titan_name)
        player.add_xp(20)
        player.coins += 10
        if not player.active_titan:
            player.active_titan = self.titan_name
        GameState.save_player(player)

        stats  = TITAN_STATS[self.titan_name]
        rarity = stats["rarity"]
        embed  = discord.Embed(
            title="🎉 Titan Captured!",
            description=(
                f"{interaction.user.mention} caught a **{RARITY_EMOJI[rarity]} {self.titan_name}**!\n"
                f"You now have **{player.collection[self.titan_name]}x {self.titan_name}**."
            ),
            color=RARITY_COLOR[rarity]
        )
        embed.set_image(url=TITAN_IMAGES.get(self.titan_name, SURVEY_CORPS_ICON))
        embed.add_field(name="💰 Coins Earned", value="+10",  inline=True)
        embed.add_field(name="⚡ XP Earned",    value="+20",  inline=True)
        embed.add_field(name="🗂️ Total Titans", value=player.total_titans(), inline=True)
        embed.set_footer(text="Use >collection to view your titans | >setactive to pick your battle titan")
        await interaction.response.send_message(embed=embed)

    async def on_timeout(self):
        """Called when nobody catches the titan in time."""
        spawn = _active_spawns.get(self.guild_id)
        if spawn and not spawn["caught"]:
            _active_spawns.pop(self.guild_id, None)
            timeout_embed = discord.Embed(
                title="🚨 Titan Escaped!",
                description=f"**{self.titan_name}** disappeared back into the wilderness... nobody was fast enough!",
                color=0xFF3333
            )
            timeout_embed.set_thumbnail(url=TITAN_IMAGES.get(self.titan_name, SURVEY_CORPS_ICON))
            await self.channel.send(embed=timeout_embed)


class TitanCatch(commands.Cog):
    """Spawn + catch system, collection viewer, and scouting commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.auto_spawn.start()

    def cog_unload(self):
        self.auto_spawn.cancel()

    # ── Auto-spawn loop ────────────────────────────────────────────────────
    @tasks.loop(seconds=60)
    async def auto_spawn(self):
        """Every minute, check if a guild is due for a new spawn."""
        if not hasattr(self, "_next_spawn"):
            self._next_spawn = {}
        import time
        now = time.time()
        for guild in self.bot.guilds:
            channel_id = GameState.get_spawn_channel(guild.id)
            if not channel_id:
                continue
            if now < self._next_spawn.get(guild.id, 0):
                continue
            if guild.id in _active_spawns:
                continue
            channel = guild.get_channel(channel_id)
            if not channel:
                continue
            await self._do_spawn(guild.id, channel)
            self._next_spawn[guild.id] = now + random.randint(*SPAWN_INTERVAL)

    @auto_spawn.before_loop
    async def before_spawn(self):
        await self.bot.wait_until_ready()

    # ── Core spawn logic ───────────────────────────────────────────────────
    async def _do_spawn(self, guild_id: int, channel: discord.TextChannel):
        titan = _spawn_weights()
        embed = _spawn_embed(titan)
        view  = CatchView(guild_id, titan, channel)
        msg   = await channel.send(embed=embed, view=view)
        _active_spawns[guild_id] = {"titan": titan, "message_id": msg.id, "caught": False}

    # ── >setspawn ──────────────────────────────────────────────────────────
    @commands.command(name="setspawn")
    @commands.has_permissions(manage_guild=True)
    async def setspawn(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Admin: Set the titan spawn channel. Usage: >setspawn #channel"""
        ch = channel or ctx.channel
        GameState.set_spawn_channel(ctx.guild.id, ch.id)
        embed = discord.Embed(
            title="✅ Spawn Channel Set",
            description=f"Titans will now randomly spawn in {ch.mention}!",
            color=0x55AA55
        )
        embed.set_thumbnail(url=SURVEY_CORPS_ICON)
        await ctx.send(embed=embed)

    # ── >spawn (manual, admin) ─────────────────────────────────────────────
    @commands.command(name="spawn")
    @commands.has_permissions(manage_guild=True)
    async def spawn(self, ctx: commands.Context):
        """Admin: Manually force a titan spawn in the current channel."""
        if ctx.guild.id in _active_spawns:
            await ctx.send("⚠️ A titan is already active! Wait for it to be caught or to escape.")
            return
        await self._do_spawn(ctx.guild.id, ctx.channel)

    # ── >collection ────────────────────────────────────────────────────────
    @commands.command(name="collection", aliases=["col", "titans"])
    async def collection(self, ctx: commands.Context, member: discord.Member = None):
        """View your (or another user's) titan collection. Usage: >collection [@user]"""
        target = member or ctx.author
        player = GameState.get_player(str(target.id), target.display_name)

        if not player.collection:
            await ctx.send(f"{'You have' if target == ctx.author else f'{target.display_name} has'} no titans yet! Wait for one to spawn.")
            return

        # Sort by rarity
        rarity_order = {"Legendary": 0, "Epic": 1, "Rare": 2, "Uncommon": 3, "Common": 4}
        sorted_titans = sorted(
            player.collection.items(),
            key=lambda x: rarity_order.get(TITAN_STATS.get(x[0], {}).get("rarity", "Common"), 4)
        )

        lines = []
        for name, count in sorted_titans:
            stats  = TITAN_STATS.get(name, {})
            rarity = stats.get("rarity", "Common")
            active_marker = " ← Active" if name == player.active_titan else ""
            lines.append(f"{RARITY_EMOJI[rarity]} **{name}** x{count}{active_marker}")

        embed = discord.Embed(
            title=f"🗂️ {target.display_name}'s Titan Collection",
            description="\n".join(lines),
            color=0x5599FF
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="📊 Total Titans", value=player.total_titans(), inline=True)
        embed.add_field(name="🏆 Best Titan",   value=player.best_titan() or "None", inline=True)
        embed.add_field(name="⚔️ Active Titan", value=player.active_titan or "None set", inline=True)
        embed.set_footer(text="Use >setactive <titan name> to pick your battle titan")
        await ctx.send(embed=embed)

    # ── >setactive ─────────────────────────────────────────────────────────
    @commands.command(name="setactive", aliases=["sa"])
    async def setactive(self, ctx: commands.Context, *, titan_name: str):
        """Set your active titan for battles. Usage: >setactive Jaw Titan"""
        player = GameState.get_player(str(ctx.author.id), ctx.author.display_name)
        match = next((t for t in player.collection if t.lower() == titan_name.lower()), None)
        if not match:
            owned = ", ".join(player.collection.keys()) or "none"
            await ctx.send(f"❌ You don't own **{titan_name}**. Your titans: `{owned}`")
            return
        player.active_titan = match
        GameState.save_player(player)
        stats = TITAN_STATS[match]
        embed = discord.Embed(
            title="✅ Active Titan Set!",
            description=f"**{match}** is now your battle titan!",
            color=RARITY_COLOR[stats["rarity"]]
        )
        embed.set_thumbnail(url=TITAN_IMAGES.get(match, SURVEY_CORPS_ICON))
        embed.add_field(name="⚔️ ATK", value=stats["atk"], inline=True)
        embed.add_field(name="🛡️ DEF", value=stats["def"], inline=True)
        embed.add_field(name="❤️ HP",  value=stats["hp"],  inline=True)
        await ctx.send(embed=embed)

    # ── >scout ─────────────────────────────────────────────────────────────
    @commands.command(name="scout")
    async def scout(self, ctx: commands.Context, *, titan_name: str):
        """View detailed info about any titan. Usage: >scout Colossal Titan"""
        match = next((t for t in TITAN_STATS if t.lower() == titan_name.lower()), None)
        if not match:
            names = ", ".join(TITAN_STATS.keys())
            await ctx.send(f"❌ Unknown titan. Available titans: `{names}`")
            return
        stats  = TITAN_STATS[match]
        rarity = stats["rarity"]
        embed  = discord.Embed(
            title=f"{RARITY_EMOJI[rarity]} {match}",
            description=f"Detailed scouting report on the **{match}**.",
            color=RARITY_COLOR[rarity]
        )
        embed.set_image(url=TITAN_IMAGES.get(match, SURVEY_CORPS_ICON))
        embed.add_field(name="⭐ Rarity", value=f"{RARITY_EMOJI[rarity]} {rarity}", inline=True)
        embed.add_field(name="❤️ HP",     value=stats["hp"],  inline=True)
        embed.add_field(name="⚔️ ATK",    value=stats["atk"], inline=True)
        embed.add_field(name="🛡️ DEF",    value=stats["def"], inline=True)
        embed.add_field(name="💨 SPD",    value=stats["spd"], inline=True)
        weight = TITAN_WEIGHTS.get(match, 1)
        total  = sum(TITAN_WEIGHTS.values())
        chance = round(weight / total * 100, 1)
        embed.add_field(name="🎲 Spawn Chance", value=f"{chance}%", inline=True)
        await ctx.send(embed=embed)

    # ── >release ───────────────────────────────────────────────────────────
    @commands.command(name="release")
    async def release(self, ctx: commands.Context, *, titan_name: str):
        """Release a titan from your collection. Usage: >release Pure Titan"""
        player = GameState.get_player(str(ctx.author.id), ctx.author.display_name)
        match  = next((t for t in player.collection if t.lower() == titan_name.lower()), None)
        if not match:
            await ctx.send(f"❌ You don't own **{titan_name}**.")
            return
        player.collection[match] -= 1
        if player.collection[match] <= 0:
            del player.collection[match]
        if player.active_titan == match and match not in player.collection:
            player.active_titan = player.best_titan() or ""
        player.coins += 5
        GameState.save_player(player)
        await ctx.send(f"🔓 Released **{match}** and received **+5 coins**.")


async def setup(bot):
    await bot.add_cog(TitanCatch(bot))
