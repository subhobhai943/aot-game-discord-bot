import discord
from discord.ext import commands
from discord import app_commands
from aot.core.database import AoTDatabase
from aot.engine.combat import CombatSimulator
from aot.engine.odm_gear import ODMGear

db = AoTDatabase()
simulator = CombatSimulator(db)

class Battle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="simulate", description="Get a cinematic narrative battle simulation")
    @app_commands.describe(character="Scout name", titan="Titan name")
    async def simulate(self, interaction: discord.Interaction, character: str, titan: str):
        await interaction.response.defer()
        try:
            report = simulator.simulate_encounter(character, titan)
        except Exception as e:
            await interaction.followup.send(f"\u274c Simulation failed: `{e}`")
            return
        embed = discord.Embed(
            title=f"\u2694\ufe0f {character} vs {titan}",
            description=f"```\n{report[:2000]}\n```",
            color=discord.Color.red()
        )
        embed.set_footer(text="\U0001fa7a Wings of Freedom | AOT-Toolkit")
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Battle(bot))
