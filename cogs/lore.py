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
            await interaction.response.send_message(
                f"❌ Character `{name}` not found. Try names like: Levi, Mikasa, Eren, Armin.",
                ephemeral=True
            )
            return
        embed = discord.Embed(title=f"🩺 {char['full_name']}", color=discord.Color.dark_red())
        embed.add_field(name="Affiliation", value=char.get("affiliation", "Unknown"), inline=True)
        embed.add_field(name="Titan Power", value=char.get("titan_power", "None"),    inline=True)
        embed.add_field(name="Status",      value=char.get("status", "Unknown"),      inline=True)
        stats = char.get("stats", {})
        if stats:
            stat_txt = "  ".join(f"**{k.upper()[:3]}** {v}" for k, v in stats.items())
            embed.add_field(name="Combat Stats", value=stat_txt, inline=False)
        embed.add_field(name="Bio", value=char.get("bio", "No info available.")[:1000], inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="titan", description="Look up a Titan")
    @app_commands.describe(name="Titan name (e.g. Beast, Armored, Colossal)")
    async def titan(self, interaction: discord.Interaction, name: str):
        try:
            titan = db.get_titan(name)
        except TitanNotFoundError:
            await interaction.response.send_message(
                f"❌ Titan `{name}` not found. Try: Beast, Armored, Colossal, Female, Jaw.",
                ephemeral=True
            )
            return
        embed = discord.Embed(title=f"👹 {titan['name']}", color=discord.Color.dark_orange())
        abilities = titan.get("special_abilities", [])
        embed.add_field(name="Abilities", value=", ".join(abilities) if abilities else "None", inline=False)
        embed.add_field(name="Height",    value=f"{titan.get('height_m', '?')}m", inline=True)
        embed.add_field(name="Inheritor", value=titan.get("current_inheritor", "Unknown"), inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="quote", description="Get a random AoT quote")
    @app_commands.describe(
        tag="Optional vibe tag: motivational, dark, wisdom",
        character="Optional: filter by character name"
    )
    async def quote(
        self,
        interaction: discord.Interaction,
        tag: str = None,
        character: str = None,
    ):
        """Fixed: handles missing tag/character gracefully with helpful error."""
        try:
            q = db.get_random_quote(character=character, tag=tag)
        except QuoteNotFoundError:
            filters = []
            if tag:
                filters.append(f"tag=`{tag}`")
            if character:
                filters.append(f"character=`{character}`")
            hint = " & ".join(filters) if filters else "those filters"
            await interaction.response.send_message(
                f"❌ No quote found for {hint}.\n"
                f"💡 Try tags: `motivational`, `dark`, `wisdom` — or leave blank for any quote.",
                ephemeral=True
            )
            return
        embed = discord.Embed(
            description=f'*“{q["quote_text"]}”*',
            color=discord.Color.gold()
        )
        tags_txt = ", ".join(q.get("vibe_tags", []))
        embed.set_footer(text=f"— {q['character_name']}" + (f"  •  {tags_txt}" if tags_txt else ""))
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Lore(bot))
