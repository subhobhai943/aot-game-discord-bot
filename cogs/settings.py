"""Server settings: custom prefix management."""
import json
import os
import time
import psutil
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

    @app_commands.command(name="set-prefix", description="Set a custom command prefix for this server")
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

    def _get_resources_embed(self) -> discord.Embed:
        # CPU
        cpu_percent = psutil.cpu_percent(interval=None)
        cpu_count = psutil.cpu_count()
        
        # Memory
        mem = psutil.virtual_memory()
        mem_total_gb = mem.total / (1024 ** 3)
        mem_used_gb = mem.used / (1024 ** 3)
        mem_percent = mem.percent
        
        # Disk
        disk = psutil.disk_usage('/')
        disk_total_gb = disk.total / (1024 ** 3)
        disk_used_gb = disk.used / (1024 ** 3)
        disk_percent = disk.percent
        
        # Uptime
        boot_time = psutil.boot_time()
        uptime_sec = time.time() - boot_time
        days, rem = divmod(int(uptime_sec), 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{days}d {hours}h {minutes}m" if days else f"{hours}h {minutes}m"
        
        # Process (Bot)
        proc = psutil.Process()
        bot_mem_mb = proc.memory_info().rss / (1024 ** 2)
        
        # Gateway latency
        latency_ms = round(self.bot.latency * 1000)
        
        def progress_bar(percent: float, size: int = 12) -> str:
            filled = min(size, max(0, round(percent / 100 * size)))
            return f"`{'█' * filled}{'░' * (size - filled)}` {percent:.1f}%"
            
        embed = discord.Embed(
            title="🖥️ Server Resources & Load Status",
            color=discord.Color.dark_theme() if cpu_percent < 80 else discord.Color.red(),
        )
        
        embed.add_field(
            name="💻 CPU Load",
            value=f"{progress_bar(cpu_percent)}\n*{cpu_count} Cores / Threads*",
            inline=True
        )
        embed.add_field(
            name="💾 System RAM",
            value=f"{progress_bar(mem_percent)}\n*{mem_used_gb:.2f} GB / {mem_total_gb:.2f} GB*",
            inline=True
        )
        embed.add_field(
            name="💽 Disk Storage",
            value=f"{progress_bar(disk_percent)}\n*{disk_used_gb:.1f} GB / {disk_total_gb:.1f} GB*",
            inline=True
        )
        
        embed.add_field(
            name="🤖 Bot RAM Usage",
            value=f"`{bot_mem_mb:.1f} MB`",
            inline=True
        )
        embed.add_field(
            name="⚡ API Latency",
            value=f"`{latency_ms} ms`",
            inline=True
        )
        embed.add_field(
            name="⏱️ System Uptime",
            value=f"`{uptime_str}`",
            inline=True
        )
        
        embed.set_footer(text="AoT Game Bot  •  Auto-updated on request")
        return embed

    @commands.command(name="resources", help="Check the current server usage and load.")
    async def resources_prefix(self, ctx: commands.Context):
        embed = self._get_resources_embed()
        await ctx.send(embed=embed)

    @app_commands.command(name="resources", description="Check the current server usage and load")
    async def resources_slash(self, interaction: discord.Interaction):
        embed = self._get_resources_embed()
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Settings(bot))
