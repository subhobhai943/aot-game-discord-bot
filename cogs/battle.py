import discord
from discord.ext import commands
from discord import app_commands
from aot.core.database import AoTDatabase
from aot.engine.combat import CombatSimulator

db = AoTDatabase()
simulator = CombatSimulator(db)

class Battle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="battle", description="Simulate a battle between a character and a titan!")
    @app_commands.describe(
        character="Scout name (e.g. Levi Ackerman)",
        titan="Titan name (e.g. Beast Titan)"
    )
    async def battle(self, interaction: discord.Interaction, character: str, titan: str):
        await interaction.response.defer()

        try:
            report = simulator.simulate_encounter(character, titan)
        except Exception as e:
            await interaction.followup.send(f"❌ Battle simulation failed: `{e}`")
            return

        embed = discord.Embed(
            title=f"⚔️ {character} vs {titan}",
            description=f"```\n{report[:2000]}\n```",
            color=discord.Color.red()
        )
        embed.set_footer(text="🪽 Wings of Freedom | AOT-Toolkit")
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Battle(bot))
