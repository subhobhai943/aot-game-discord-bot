"""Server settings: custom prefix management."""
import json
import os
import discord
from discord.ext import commands
from discord import app_commands

SETTINGS_FILE = "data/guild_settings.json"


def _load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_settings(data: dict):
    os.makedirs("data", exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_prefix(guild_id: int) -> str:
    """Return the custom prefix for a guild, default is '!'."""
    data = _load_settings()
    return data.get(str(guild_id), {}).get("prefix", "!")


class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="set_prefix", description="Set a custom command prefix for this server")
    @app_commands.describe(prefix="Your new prefix (e.g. !, ?, aot!, >)")
    @app_commands.default_permissions(manage_guild=True)  # Only admins/managers
    async def set_prefix(
        self,
        interaction: discord.Interaction,
        prefix: str,
    ):
        if len(prefix) > 5:
            await interaction.response.send_message(
                "❌ Prefix must be 5 characters or fewer.", ephemeral=True
            )
            return

        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server.", ephemeral=True
            )
            return

        data = _load_settings()
        gid = str(interaction.guild_id)
        if gid not in data:
            data[gid] = {}
        data[gid]["prefix"] = prefix
        _save_settings(data)

        embed = discord.Embed(
            title="⚙️ Prefix Updated",
            description=f"Server prefix has been set to `{prefix}`\n\nExample: `{prefix}help`",
            color=discord.Color.green(),
        )
        embed.set_footer(text="Slash commands (/) always work regardless of prefix.")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="prefix", description="Check the current command prefix for this server")
    async def check_prefix(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("❌ Server only command.", ephemeral=True)
            return
        p = get_prefix(interaction.guild_id)
        embed = discord.Embed(
            title="ℹ️ Current Prefix",
            description=f"This server's prefix is: `{p}`",
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="Use /set_prefix to change it (requires Manage Server permission).")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Settings(bot))
