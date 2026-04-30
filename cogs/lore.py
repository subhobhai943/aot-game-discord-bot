import discord
from discord.ext import commands
from discord import app_commands
from aot.core.database import AoTDatabase
from aot.core.exceptions import CharacterNotFoundError, TitanNotFoundError, QuoteNotFoundError

db = AoTDatabase()

class Lore(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="character", description="Look up an AoT character")
    @app_commands.describe(name="Character name (e.g. Levi, Mikasa)")
    async def character(self, interaction: discord.Interaction, name: str):
        try:
            char = db.get_character(name)
        except CharacterNotFoundError:
            await interaction.response.send_message(f"\u274c Character `{name}` not found.", ephemeral=True)
            return
        embed = discord.Embed(title=f"\U0001fa7a {char['full_name']}", color=discord.Color.dark_red())
        embed.add_field(name="Affiliation",  value=char.get("affiliation", "Unknown"),   inline=True)
        embed.add_field(name="Titan Power",  value=char.get("titan_power", "None"),      inline=True)
        embed.add_field(name="Status",       value=char.get("status", "Unknown"),        inline=True)
        stats = char.get("stats", {})
        if stats:
            stat_txt = "  ".join(f"**{k.upper()[:3]}** {v}" for k,v in stats.items())
            embed.add_field(name="Combat Stats", value=stat_txt, inline=False)
        embed.add_field(name="Bio", value=char.get("bio", "No info available.")[:1000], inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="titan", description="Look up a Titan")
    @app_commands.describe(name="Titan name (e.g. Beast, Armored)")
    async def titan(self, interaction: discord.Interaction, name: str):
        try:
            titan = db.get_titan(name)
        except TitanNotFoundError:
            await interaction.response.send_message(f"\u274c Titan `{name}` not found.", ephemeral=True)
            return
        embed = discord.Embed(title=f"\U0001f479 {titan['name']}", color=discord.Color.dark_orange())
        abilities = titan.get("special_abilities", [])
        embed.add_field(name="Abilities",   value=", ".join(abilities) if abilities else "None", inline=False)
        embed.add_field(name="Height",      value=f"{titan.get('height_m', '?')}m", inline=True)
        embed.add_field(name="Inheritor",   value=titan.get("current_inheritor", "Unknown"),     inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="quote", description="Get a random AoT quote")
    @app_commands.describe(tag="Optional vibe tag: motivational, dark, wisdom")
    async def quote(self, interaction: discord.Interaction, tag: str = None):
        try:
            q = db.get_random_quote(tag=tag)
        except QuoteNotFoundError:
            await interaction.response.send_message("\u274c No quote found for that tag.", ephemeral=True)
            return
        embed = discord.Embed(description=f'*"{q["quote_text"]}"*', color=discord.Color.gold())
        embed.set_footer(text=f"\u2014 {q['character_name']}")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Lore(bot))
