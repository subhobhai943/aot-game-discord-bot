"""Titan Shifter Serum Laboratory and Fusion upgrade system cog."""
from __future__ import annotations
import discord
from discord.ext import commands
from discord import app_commands
from utils.game_state import (
    GameState, TITAN_STATS, RARITY_COLOR, RARITY_EMOJI, get_titan_image, attach_image
)
from utils.gifs import get_gif


SERUM_YIELD = {
    "Common": 1,
    "Uncommon": 3,
    "Rare": 8,
    "Epic": 18,
    "Legendary": 40
}


def _get_serum_yield(titan_name: str) -> int:
    stats = TITAN_STATS.get(titan_name, {"rarity": "Common"})
    rarity = stats.get("rarity", "Common")
    return SERUM_YIELD.get(rarity, 1)


class LabView(discord.ui.View):
    """Interactive Laboratory upgrade view with buttons."""

    def __init__(self, author: discord.User | discord.Member, bot: commands.Bot):
        super().__init__(timeout=120)
        self.author = author
        self.bot = bot

    def _build_lab_embed(self, player) -> discord.Embed:
        # Calculate active bonuses
        atk_pct = player.lab_atk * 5
        def_pct = player.lab_def * 5
        spd_pct = player.lab_spd * 5
        hp_pct = player.lab_hp * 10

        embed = discord.Embed(
            title="🔬 Jaeger Titan Shifter Laboratory",
            description=(
                f"Welcome, **{player.username}**! Melt duplicate Titans down into **Shifter Serum**, "
                f"then inject it to permanently upgrade your combat capabilities.\n\n"
                f"🧪 **Serum Stockpile:** `{player.serum} Serum` | 🪙 **Coins:** `{player.coins}`"
            ),
            color=0x9B59B6
        )

        def progress_bar(val: int, max_val: int = 10) -> str:
            return f"`{'█' * val}{'░' * (max_val - val)}`"

        embed.add_field(
            name=f"🧬 Titan Spinal Fluid (ATK +5%) — Level {player.lab_atk}/10",
            value=f"{progress_bar(player.lab_atk)} | *Current Bonus:* `+{atk_pct}% ATK`\n*Upgrade Cost:* `10 Serum`",
            inline=False
        )
        embed.add_field(
            name=f"💎 Armor Hardening (DEF +5%) — Level {player.lab_def}/10",
            value=f"{progress_bar(player.lab_def)} | *Current Bonus:* `-{def_pct}% Damage Taken`\n*Upgrade Cost:* `5 Serum`",
            inline=False
        )
        embed.add_field(
            name=f"💨 ODM Gas Booster (SPD +5% Dodge) — Level {player.lab_spd}/10",
            value=f"{progress_bar(player.lab_spd)} | *Current Bonus:* `+{spd_pct}% Dodge Chance`\n*Upgrade Cost:* `5 Serum`",
            inline=False
        )
        embed.add_field(
            name=f"🩸 Regeneration Cells (HP +10%) — Level {player.lab_hp}/10",
            value=f"{progress_bar(player.lab_hp)} | *Current Bonus:* `+{hp_pct}% HP Boost`\n*Upgrade Cost:* `10 Serum`",
            inline=False
        )

        embed.set_footer(text="Use >melt <titan name> to recycle duplicate Titans into Serum!")
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Attack_on_Titan_logo.png/640px-Attack_on_Titan_logo.png")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "❌ This laboratory session belongs to someone else!",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="ATK Fluid (10s)", style=discord.ButtonStyle.danger, emoji="🧬", row=0)
    async def upgrade_atk(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        player = await GameState.get_player(str(self.author.id), self.author.display_name)
        if player.lab_atk >= 10:
            await interaction.followup.send("❌ Titan Spinal Fluid upgrade has already reached MAX level (10)!", ephemeral=True)
            return
        if player.serum < 10:
            await interaction.followup.send(f"❌ You don't have enough Shifter Serum! You need `10 Serum` but only have `{player.serum}`.", ephemeral=True)
            return

        player.serum -= 10
        player.lab_atk += 1
        await GameState.save_player(player)

        embed = discord.Embed(
            title="🧬 Spinal Fluid Injected!",
            description=(
                f"**{self.author.mention}** injected Titan Spinal Fluid!\n"
                f"📈 **Attack Level:** `{player.lab_atk}/10` (+{player.lab_atk * 5}% Damage)"
            ),
            color=discord.Color.red()
        )
        gif = await get_gif("scream")
        if gif:
            embed.set_image(url=gif)

        await interaction.message.edit(embed=self._build_lab_embed(player), view=self)
        await interaction.followup.send(embed=embed)

    @discord.ui.button(label="DEF Hardening (5s)", style=discord.ButtonStyle.primary, emoji="💎", row=0)
    async def upgrade_def(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        player = await GameState.get_player(str(self.author.id), self.author.display_name)
        if player.lab_def >= 10:
            await interaction.followup.send("❌ Armor Hardening upgrade has already reached MAX level (10)!", ephemeral=True)
            return
        if player.serum < 5:
            await interaction.followup.send(f"❌ You don't have enough Shifter Serum! You need `5 Serum` but only have `{player.serum}`.", ephemeral=True)
            return

        player.serum -= 5
        player.lab_def += 1
        await GameState.save_player(player)

        embed = discord.Embed(
            title="💎 Hardening Serum Injected!",
            description=(
                f"**{self.author.mention}** injected Armor Hardening Serum!\n"
                f"📈 **Defense Level:** `{player.lab_def}/10` (-{player.lab_def * 5}% Damage Taken)"
            ),
            color=discord.Color.blue()
        )
        gif = await get_gif("armored")
        if gif:
            embed.set_image(url=gif)

        await interaction.message.edit(embed=self._build_lab_embed(player), view=self)
        await interaction.followup.send(embed=embed)

    @discord.ui.button(label="SPD Booster (5s)", style=discord.ButtonStyle.success, emoji="💨", row=0)
    async def upgrade_spd(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        player = await GameState.get_player(str(self.author.id), self.author.display_name)
        if player.lab_spd >= 10:
            await interaction.followup.send("❌ ODM Gas Booster upgrade has already reached MAX level (10)!", ephemeral=True)
            return
        if player.serum < 5:
            await interaction.followup.send(f"❌ You don't have enough Shifter Serum! You need `5 Serum` but only have `{player.serum}`.", ephemeral=True)
            return

        player.serum -= 5
        player.lab_spd += 1
        await GameState.save_player(player)

        embed = discord.Embed(
            title="💨 ODM Gas Booster Injected!",
            description=(
                f"**{self.author.mention}** injected ODM Gas Booster Serum!\n"
                f"📈 **Speed Level:** `{player.lab_spd}/10` (+{player.lab_spd * 5}% Evasion / Dodge Chance)"
            ),
            color=discord.Color.green()
        )
        gif = await get_gif("odm")
        if gif:
            embed.set_image(url=gif)

        await interaction.message.edit(embed=self._build_lab_embed(player), view=self)
        await interaction.followup.send(embed=embed)

    @discord.ui.button(label="HP Regen (10s)", style=discord.ButtonStyle.secondary, emoji="🩸", row=0)
    async def upgrade_hp(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        player = await GameState.get_player(str(self.author.id), self.author.display_name)
        if player.lab_hp >= 10:
            await interaction.followup.send("❌ Regeneration Cells upgrade has already reached MAX level (10)!", ephemeral=True)
            return
        if player.serum < 10:
            await interaction.followup.send(f"❌ You don't have enough Shifter Serum! You need `10 Serum` but only have `{player.serum}`.", ephemeral=True)
            return

        player.serum -= 10
        player.lab_hp += 1
        await GameState.save_player(player)

        embed = discord.Embed(
            title="🩸 Regeneration Cells Injected!",
            description=(
                f"**{self.author.mention}** injected Regeneration Cells Fluid!\n"
                f"📈 **HP Level:** `{player.lab_hp}/10` (+{player.lab_hp * 10}% Maximum Health)"
            ),
            color=discord.Color.magenta()
        )
        gif = await get_gif("transform")
        if gif:
            embed.set_image(url=gif)

        await interaction.message.edit(embed=self._build_lab_embed(player), view=self)
        await interaction.followup.send(embed=embed)


class Laboratory(commands.Cog):
    """🔬 Permanent character upgrade systems using recycled Titans."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Prefix Melt Command ───────────────────────────────────────────────────
    @commands.command(name="melt", help="Melt down a duplicate Titan for Shifter Serum. Usage: >melt Jaw Titan")
    async def melt_prefix(self, ctx: commands.Context, *, titan_name: str):
        player = await GameState.get_player(str(ctx.author.id), ctx.author.display_name)
        match = next((t for t in player.collection if t.lower() == titan_name.lower()), None)
        if not match:
            await ctx.send(f"❌ You don't own **{titan_name}**.")
            return

        count = player.collection[match]
        if count <= 1:
            await ctx.send(
                f"⚠️ **{match}** is your last copy of this Titan! You must own duplicate copies (count > 1) to melt them down "
                f"so you don't lose access to them."
            )
            return

        # Deduct 1 duplicate and award serum
        player.collection[match] -= 1
        if player.collection[match] <= 0:
            del player.collection[match]
            
        yield_amount = _get_serum_yield(match)
        player.serum += yield_amount
        await GameState.save_player(player)

        stats = TITAN_STATS[match]
        rarity = stats["rarity"]

        embed = discord.Embed(
            title="🔬 Extraction Successful!",
            description=(
                f"Melting down 1 duplicate **{match}** yielded:\n"
                f"🧪 **+{yield_amount} Shifter Serum**!\n\n"
                f"New Stockpile: `{player.serum} Serum` | Remaining duplicates: `{player.collection.get(match, 0)}`"
            ),
            color=RARITY_COLOR[rarity]
        )
        file = attach_image(embed, get_titan_image(match), as_thumbnail=True)
        await ctx.send(embed=embed, file=file)

    # ── Slash Melt Command ────────────────────────────────────────────────────
    @app_commands.command(name="melt", description="Melt down duplicate Titans for Shifter Serum")
    @app_commands.describe(titan="Select the Titan duplicate to melt down")
    async def melt_slash(self, interaction: discord.Interaction, titan: str):
        await interaction.response.defer()
        player = await GameState.get_player(str(interaction.user.id), interaction.user.display_name)
        match = next((t for t in player.collection if t.lower() == titan.lower()), None)
        if not match:
            await interaction.followup.send(f"❌ You don't own **{titan}**.", ephemeral=True)
            return

        count = player.collection[match]
        if count <= 1:
            await interaction.followup.send(
                f"⚠️ **{match}** is your last copy of this Titan! You must own duplicate copies to recycle them safely.",
                ephemeral=True
            )
            return

        player.collection[match] -= 1
        if player.collection[match] <= 0:
            del player.collection[match]

        yield_amount = _get_serum_yield(match)
        player.serum += yield_amount
        await GameState.save_player(player)

        stats = TITAN_STATS[match]
        rarity = stats["rarity"]

        embed = discord.Embed(
            title="🔬 Extraction Successful!",
            description=(
                f"Melting down 1 duplicate **{match}** yielded:\n"
                f"🧪 **+{yield_amount} Shifter Serum**!\n\n"
                f"New Stockpile: `{player.serum} Serum` | Remaining copies: `{player.collection.get(match, 0)}`"
            ),
            color=RARITY_COLOR[rarity]
        )
        file = attach_image(embed, get_titan_image(match), as_thumbnail=True)
        if file:
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send(embed=embed)

    # ── Prefix Lab Command ───────────────────────────────────────────────────
    @commands.command(name="laboratory", aliases=["lab"], help="Open the Shifter Serum Upgrade Laboratory.")
    async def lab_prefix(self, ctx: commands.Context):
        player = await GameState.get_player(str(ctx.author.id), ctx.author.display_name)
        view = LabView(ctx.author, self.bot)
        embed = view._build_lab_embed(player)
        await ctx.send(embed=embed, view=view)

    # ── Slash Lab Command ────────────────────────────────────────────────────
    @app_commands.command(name="laboratory", description="Open the Shifter Serum Upgrade Laboratory")
    async def lab_slash(self, interaction: discord.Interaction):
        player = await GameState.get_player(str(interaction.user.id), interaction.user.display_name)
        view = LabView(interaction.user, self.bot)
        embed = view._build_lab_embed(player)
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Laboratory(bot))
