import discord
from discord.ext import commands
from discord import app_commands
from aot.core.database import AoTDatabase

db = AoTDatabase()

class Lore(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="character", description="Look up an AoT character")
    @app_commands.describe(name="Character name (e.g. Levi, Mikasa)")
    async def character(self, interaction: discord.Interaction, name: str):
        char = db.get_character(name)
        if not char:
            await interaction.response.send_message(f"❌ Character `{name}` not found.", ephemeral=True)
            return
        embed = discord.Embed(
            title=f"🗡️ {char['full_name']}",
            color=discord.Color.dark_red()
        )
        embed.add_field(name="Affiliation", value=char.get("affiliation", "Unknown"), inline=True)
        embed.add_field(name="Titan Power", value=char.get("titan_power", "None"), inline=True)
        embed.add_field(name="Status", value=char.get("status", "Unknown"), inline=True)
        embed.add_field(name="Bio", value=char.get("bio", "No info available."), inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="quote", description="Get a random AoT quote")
    @app_commands.describe(tag="Optional tag: motivational, dark, wisdom")
    async def quote(self, interaction: discord.Interaction, tag: str = None):
        q = db.get_random_quote(tag=tag)
        if not q:
            await interaction.response.send_message("❌ No quote found for that tag.", ephemeral=True)
            return
        embed = discord.Embed(
            description=f'*"{q["quote_text"]}"*',
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"— {q['character_name']}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="titan", description="Look up a Titan")
    @app_commands.describe(name="Titan name (e.g. Beast, Armored)")
    async def titan(self, interaction: discord.Interaction, name: str):
        titan = db.get_titan(name)
        if not titan:
            await interaction.response.send_message(f"❌ Titan `{name}` not found.", ephemeral=True)
            return
        embed = discord.Embed(
            title=f"👹 {titan['name']}",
            color=discord.Color.dark_orange()
        )
        embed.add_field(name="Abilities", value=", ".join(titan.get("special_abilities", [])), inline=False)
        embed.add_field(name="Height", value=titan.get("height_m", "Unknown"), inline=True)
        embed.add_field(name="Current Inheritor", value=titan.get("current_inheritor", "Unknown"), inline=True)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Lore(bot))
