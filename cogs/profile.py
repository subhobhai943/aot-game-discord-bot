import discord
from discord.ext import commands
from discord import app_commands
from utils.game_state import GameState, CHARACTERS
from utils.image_gen import generate_profile_card


class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="profile", description="View your own or another user's Scout profile card")
    @app_commands.describe(user="Mention a user to view their profile (leave blank for your own)")
    async def profile(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        player = GameState.get_player(str(target.id), target.display_name)

        img_buf = generate_profile_card(
            username=target.display_name,
            scout_name=player.scout_name,
            level=player.level,
            xp=player.xp,
            xp_needed=player.xp_needed,
            wins=player.wins,
            losses=player.losses,
            kills=player.kills,
            rank=player.rank,
        )

        file = discord.File(fp=img_buf, filename="profile.png")
        is_own = target.id == interaction.user.id
        title = (
            f"🩺 {target.display_name}'s Scout Profile"
            if not is_own
            else f"🩺 Your Scout Profile"
        )
        embed = discord.Embed(title=title, color=discord.Color.teal())
        embed.set_thumbnail(url=target.display_avatar.url)  # Shows their Discord PFP
        embed.add_field(name="Discord", value=target.mention, inline=True)
        embed.add_field(name="Scout",   value=player.scout_name, inline=True)
        embed.add_field(name="Rank",    value=player.rank,        inline=True)
        embed.set_image(url="attachment://profile.png")
        await interaction.response.send_message(embed=embed, file=file)

    @app_commands.command(name="choose_scout", description="Choose your scout character for battles")
    @app_commands.describe(character="Scout name to play as")
    @app_commands.choices(character=[
        app_commands.Choice(name=c, value=c) for c in CHARACTERS
    ])
    async def choose_scout(
        self,
        interaction: discord.Interaction,
        character: app_commands.Choice[str],
    ):
        player = GameState.get_player(str(interaction.user.id), interaction.user.display_name)
        player.scout_name = character.value
        GameState.save_player(player)
        await interaction.response.send_message(
            f"✅ You are now playing as **{character.value}**!\nUse `/fight` to start a battle.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Profile(bot))
