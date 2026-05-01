"""Mikasa Ackerman-specific commands and features."""
import discord
from discord.ext import commands
from discord import app_commands
from utils.gifs import get_gif
from utils.game_state import GameState, RANKS

class Mikasa(commands.Cog):
    """Mikasa Ackerman themed commands and interactions."""

    def __init__(self, bot):
        self.bot = bot

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

    @app_commands.command(name="ackerman_bond", description="See your Ackerman-style bond with another user")
    async def ackerman_bond(self, interaction: discord.Interaction, user: discord.Member):
        """Calculate an 'Ackerman bond' score between two users."""
        author = interaction.user
        
        # Deterministic but seemingly random bond score
        combined = hash(str(author.id) + str(user.id)) % 100 + 1
        
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
        
        embed = discord.Embed(
            title=f"🧩 Ackerman Bond: {author.display_name} & {user.display_name}",
            description=f"**Bond Strength:** {combined}/100\n\n{rating}",
            color=color
        )
        # Add Ackerman-themed stats
        embed.add_field(name="🛡️ Protection Level", value="🔥" * (combined // 20) + "⬜" * (5 - combined // 20), inline=True)
        embed.add_field(name="❤️ Devotion", value="❤" * (combined // 25) + "⬜" * (4 - combined // 25), inline=True)
        embed.set_footer(text="Eren... for all these years, I've liked you.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="mikasa_stats", description="View Mikasa Ackerman's combat statistics")
    async def mikasa_stats(self, interaction: discord.Interaction):
        """Display detailed Mikasa Ackerman combat stats."""
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
        embed.add_field(name="Kills (Estimated)", value="100+ Titans (Including War Hammer Titan)", inline=True)
        embed.add_field(name="Status", value="Active - Protecting Paradis", inline=True)
        embed.set_thumbnail(url="https://static.wikia.nocookie.net/shingekinokyojin/images/3/37/Mikasa_Ackerman.png/revision/latest/scale-to-width-down/400")
        embed.set_footer(text="🧩 Wings of Freedom | Eren... I've always been with you.")
        await interaction.response.send_message(embed=embed)

    @commands.command(name="mikasa")
    async def mikasa_react(self, ctx, member: discord.Member = None):
        """Send a Mikasa-themed reaction."""
        target = member.display_name if member else "everyone"
        author = ctx.author.display_name
        gif_url = await get_gif("mikasa_protect", "mikasa protect anime")
        
        embed = discord.Embed(
            title="⚔️ Mikasa's Protection",
            description=f"**{author} protects {target} with Mikasa's devotion! ⚔️**",
            color=discord.Color.dark_red()
        )
        if gif_url:
            embed.set_image(url=gif_url)
        embed.set_footer(text="🧩 A Wings of Freedom")
        await ctx.send(embed=embed)

    @commands.command(name="red_scarf")
    async def red_scarf(self, ctx, member: discord.Member = None):
        """Mikasa's iconic red scarf action."""
        target = member.display_name if member else "everyone"
        author = ctx.author.display_name
        gif_url = await get_gif("mikasa_scarf", "mikasa red scarf anime")
        
        embed = discord.Embed(
            title="🧣 Red Scarf of Devotion",
            description=f"**{author} wraps the red scarf around {target}**, keeping them safe in this cruel world 🧣",
            color=discord.Color.red()
        )
        if gif_url:
            embed.set_image(url=gif_url)
        embed.set_footer(text="❤️ I want to be with you... always.")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Mikasa(bot))
