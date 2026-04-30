import discord
from discord.ext import commands
from discord import app_commands
from aot.engine.odm_gear import ODMGear

class ODM(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="odm_grapple", description="Simulate an ODM gear grapple!")
    @app_commands.describe(
        distance="Distance in meters (10–200)",
        speed="Speed: slow, normal, or fast",
        gas="Starting gas capacity (default 100)"
    )
    async def odm_grapple(self, interaction: discord.Interaction,
                          distance: int, speed: str = "normal", gas: int = 100):
        if speed not in ("slow", "normal", "fast"):
            await interaction.response.send_message("❌ Speed must be `slow`, `normal`, or `fast`.", ephemeral=True)
            return
        if not (10 <= distance <= 200):
            await interaction.response.send_message("❌ Distance must be between 10 and 200 meters.", ephemeral=True)
            return

        gear = ODMGear(gas_capacity=float(gas), blade_durability=100)
        result = gear.grapple(distance_m=float(distance), speed=speed)

        embed = discord.Embed(title="🪂 ODM Gear Grapple Result", color=discord.Color.teal())
        embed.add_field(name="Distance", value=f"{distance}m", inline=True)
        embed.add_field(name="Speed", value=speed.capitalize(), inline=True)
        embed.add_field(name="Result", value=f"```{result}```", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="odm_strike", description="Simulate a nape strike on a titan!")
    @app_commands.describe(
        armor_level="Titan armor level (0–5)",
        abilities="Comma-separated abilities e.g. hardened_armor,high_endurance"
    )
    async def odm_strike(self, interaction: discord.Interaction,
                         armor_level: int = 0, abilities: str = ""):
        titan_abilities = [a.strip() for a in abilities.split(",") if a.strip()]
        gear = ODMGear(gas_capacity=100.0, blade_durability=100)
        result = gear.attack_nape(titan_armor_level=armor_level, titan_abilities=titan_abilities)

        embed = discord.Embed(title="🗡️ Nape Strike Result", color=discord.Color.dark_red())
        embed.add_field(name="Armor Level", value=armor_level, inline=True)
        embed.add_field(name="Titan Abilities", value=abilities or "None", inline=True)
        embed.add_field(name="Outcome", value=f"```{result}```", inline=False)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(ODM(bot))
