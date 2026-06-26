"""Shop and Gacha system: Recruit Titans, buy XP manuals, and open mystery chests using coins."""
from __future__ import annotations
import random
import discord
from discord.ext import commands
from discord import app_commands
from utils.game_state import (
    GameState, TITAN_STATS, TITAN_WEIGHTS, get_titan_image, attach_image,
    RARITY_COLOR, RARITY_EMOJI, SURVEY_CORPS_ICON
)
from utils.gifs import get_gif


def _roll_gacha_titan() -> str:
    """Roll a random Titan name based on standard spawn weights."""
    names = list(TITAN_WEIGHTS.keys())
    weights = list(TITAN_WEIGHTS.values())
    return random.choices(names, weights=weights, k=1)[0]


class ShopView(discord.ui.View):
    """Main interactive Shop UI view with buttons."""

    def __init__(self, author: discord.User | discord.Member, bot: commands.Bot):
        super().__init__(timeout=120)
        self.author = author
        self.bot = bot

    def _build_shop_embed(self, player) -> discord.Embed:
        embed = discord.Embed(
            title="🛒 Scout Supplies & Gacha Shop",
            description=(
                f"Welcome to the Regiment Store, **{player.username}**!\n"
                f"Spend your hard-earned coins here to level up or expand your squad.\n\n"
                f"💰 **Your Balance:** `{player.coins} coins` | 🎖️ **Level:** `{player.level}`"
            ),
            color=0xF1C40F
        )
        embed.add_field(
            name="🏍️ Titan Recruitment (Gacha) — 150 Coins",
            value="Summon a random Titan to join your collection. Standard rarity rates apply.",
            inline=False
        )
        embed.add_field(
            name="📖 Scout Training Manual — 100 Coins",
            value="Instantly gain **100 XP** to level up your character.",
            inline=False
        )
        embed.add_field(
            name="📦 Mystery Supplies Chest — 75 Coins",
            value="Open a chest for a surprise! Contains Coins (40%), XP (40%), or a random Titan (20%).",
            inline=False
        )
        embed.set_footer(text="Select a button below to purchase items.")
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Attack_on_Titan_logo.png/640px-Attack_on_Titan_logo.png")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "❌ You cannot interact with someone else's shop menu!",
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Recruit Titan (150c)", style=discord.ButtonStyle.primary, emoji="🏍️", row=0)
    async def recruit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        player = await GameState.get_player(str(self.author.id), self.author.display_name)
        if player.coins < 150:
            await interaction.followup.send(
                f"❌ You don't have enough coins! You need `150 coins` but only have `{player.coins} coins`.",
                ephemeral=True
            )
            return

        # Deduct coins and roll gacha
        player.coins -= 150
        titan_name = _roll_gacha_titan()
        player.add_titan(titan_name)
        if not player.active_titan:
            player.active_titan = titan_name
        await GameState.save_player(player)

        stats = TITAN_STATS[titan_name]
        rarity = stats["rarity"]
        color = RARITY_COLOR[rarity]

        embed = discord.Embed(
            title="✨ Gacha Recruitment Successful!",
            description=(
                f"**{self.author.mention}** spent **150 coins** and successfully recruited a Titan!\n\n"
                f"🎉 You obtained: **{RARITY_EMOJI[rarity]} {titan_name}** ({rarity} Rarity)!\n"
                f"You now own **{player.collection[titan_name]}x {titan_name}**."
            ),
            color=color
        )
        embed.add_field(name="⚔️ ATK", value=stats["atk"], inline=True)
        embed.add_field(name="🛡️ DEF", value=stats["def"], inline=True)
        embed.add_field(name="💨 SPD", value=stats["spd"], inline=True)
        embed.add_field(name="❤️ HP",  value=stats["hp"],  inline=True)
        
        file = attach_image(embed, get_titan_image(titan_name))
        
        # Update shop menu to reflect new balance
        await interaction.message.edit(embed=self._build_shop_embed(player), view=self)
        
        # Send outcome
        if file:
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send(embed=embed)

    @discord.ui.button(label="Training Manual (100c)", style=discord.ButtonStyle.success, emoji="📖", row=0)
    async def training_manual_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        player = await GameState.get_player(str(self.author.id), self.author.display_name)
        if player.coins < 100:
            await interaction.followup.send(
                f"❌ You don't have enough coins! You need `100 coins` but only have `{player.coins} coins`.",
                ephemeral=True
            )
            return

        # Deduct coins and add XP
        player.coins -= 100
        leveled_up = player.add_xp(100)
        await GameState.save_player(player)

        embed = discord.Embed(
            title="📖 Training Manual Purchased!",
            description=(
                f"**{self.author.mention}** spent **100 coins** on tactical training.\n\n"
                f"✨ You gained **+100 XP**!\n"
                f"📈 **Current XP:** `{player.xp}/{player.xp_needed}`"
            ),
            color=discord.Color.green()
        )
        if leveled_up:
            embed.add_field(
                name="🎉 LEVEL UP!",
                value=f"You have reached **Level {player.level}**! Your rank is now **{player.rank}**.",
                inline=False
            )
            embed.color = discord.Color.gold()
        
        # Update shop menu
        await interaction.message.edit(embed=self._build_shop_embed(player), view=self)
        
        gif_url = await get_gif("salute")
        if gif_url:
            embed.set_image(url=gif_url)
            
        await interaction.followup.send(embed=embed)

    @discord.ui.button(label="Mystery Chest (75c)", style=discord.ButtonStyle.secondary, emoji="📦", row=0)
    async def mystery_chest_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        player = await GameState.get_player(str(self.author.id), self.author.display_name)
        if player.coins < 75:
            await interaction.followup.send(
                f"❌ You don't have enough coins! You need `75 coins` but only have `{player.coins} coins`.",
                ephemeral=True
            )
            return

        # Deduct coins
        player.coins -= 75
        roll = random.random()

        embed = discord.Embed(
            title="📦 Supplies Chest Opened!",
            color=discord.Color.dark_grey()
        )

        file = None
        if roll < 0.40:
            # Coin reward
            win_coins = random.randint(25, 150)
            player.coins += win_coins
            net = win_coins - 75
            net_str = f"+{net}" if net >= 0 else f"{net}"
            embed.description = (
                f"**{self.author.mention}** opened a supplies chest and found **💰 {win_coins} coins**!\n\n"
                f"💸 **Net Outcome:** `{net_str} coins`"
            )
            embed.color = discord.Color.orange() if win_coins >= 75 else discord.Color.red()
        elif roll < 0.80:
            # XP reward
            win_xp = random.randint(50, 200)
            leveled_up = player.add_xp(win_xp)
            embed.description = (
                f"**{self.author.mention}** opened a supplies chest and found a stash of tactical maps!\n\n"
                f"📈 You gained **+{win_xp} XP**!\n"
                f"✨ **Current XP:** `{player.xp}/{player.xp_needed}`"
            )
            embed.color = discord.Color.blue()
            if leveled_up:
                embed.add_field(
                    name="🎉 LEVEL UP!",
                    value=f"You have reached **Level {player.level}**!",
                    inline=False
                )
                embed.color = discord.Color.gold()
        else:
            # Titan reward
            titan_name = _roll_gacha_titan()
            player.add_titan(titan_name)
            if not player.active_titan:
                player.active_titan = titan_name
            stats = TITAN_STATS[titan_name]
            rarity = stats["rarity"]
            embed.description = (
                f"**{self.author.mention}** opened a supplies chest and a dormant Titan broke loose!\n\n"
                f"👹 You captured: **{RARITY_EMOJI[rarity]} {titan_name}** ({rarity})!\n"
                f"You now own **{player.collection[titan_name]}x {titan_name}**."
            )
            embed.color = RARITY_COLOR[rarity]
            file = attach_image(embed, get_titan_image(titan_name))

        await GameState.save_player(player)

        # Update shop menu
        await interaction.message.edit(embed=self._build_shop_embed(player), view=self)

        if file:
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send(embed=embed)


class Shop(commands.Cog):
    """🛒 Interactive Regiment Supplies and Titan Recruitment Shop."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Prefix Command ────────────────────────────────────────────────────────
    @commands.command(name="shop", help="Open the Regiment Supplies and Titan Recruitment Shop.")
    async def shop_prefix(self, ctx: commands.Context):
        player = await GameState.get_player(str(ctx.author.id), ctx.author.display_name)
        view = ShopView(ctx.author, self.bot)
        embed = view._build_shop_embed(player)
        await ctx.send(embed=embed, view=view)

    # ── Slash Command ─────────────────────────────────────────────────────────
    @app_commands.command(name="shop", description="Open the Regiment Supplies and Titan Recruitment Shop")
    async def shop_slash(self, interaction: discord.Interaction):
        player = await GameState.get_player(str(interaction.user.id), interaction.user.display_name)
        view = ShopView(interaction.user, self.bot)
        embed = view._build_shop_embed(player)
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Shop(bot))
