import discord
from discord.ext import commands
from discord import app_commands
from utils.game_state import GameState, CHARACTERS
from utils.image_gen import generate_profile_card
import io

class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="profile", description="View your Scout profile card")
    async def profile(self, interaction: discord.Interaction):
        player = GameState.get_player(str(interaction.user.id), interaction.user.display_name)
        img_buf = generate_profile_card(
            username=player.username,
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
        embed = discord.Embed(
            title=f"\U0001fa7a {interaction.user.display_name}'s Scout Profile",
            color=discord.Color.teal()
        )
        embed.set_image(url="attachment://profile.png")
        await interaction.response.send_message(embed=embed, file=file)

    @app_commands.command(name="choose_scout", description="Choose your scout character")
    @app_commands.describe(character="Scout name to play as")
    @app_commands.choices(character=[
        app_commands.Choice(name=c, value=c) for c in CHARACTERS
    ])
    async def choose_scout(self, interaction: discord.Interaction,
                            character: app_commands.Choice[str]):
        player = GameState.get_player(str(interaction.user.id), interaction.user.display_name)
        player.scout_name = character.value
        GameState.save_player(player)
        await interaction.response.send_message(
            f"\u2705 You are now playing as **{character.value}**! Use `/fight` to battle.",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(Profile(bot))
