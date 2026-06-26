"""Utility Cog: Server Info, User Info, Latency Ping, and Interactive Polls."""
from __future__ import annotations
import time
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional


class PollView(discord.ui.View):
    """Interactive Poll View supporting multiple choice and real-time progress updates."""

    def __init__(self, question: str, options: list[str]):
        super().__init__(timeout=86400)  # 24-hour timeout
        self.question = question
        self.options = options
        # Map user_id (int) -> selected_option_index (int)
        self.votes: dict[int, int] = {}
        self._build_buttons()

    def _build_buttons(self):
        for index, option in enumerate(self.options):
            btn = discord.ui.Button(
                label=f"{index + 1}. {option[:50]}",
                style=discord.ButtonStyle.primary,
                custom_id=f"poll_opt_{index}"
            )
            btn.callback = self._make_callback(index)
            self.add_item(btn)

    def _make_callback(self, index: int):
        async def callback(interaction: discord.Interaction):
            user_id = interaction.user.id
            # Record or change vote
            self.votes[user_id] = index
            
            # Rebuild embed and edit
            embed = self._build_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        return callback

    def _build_embed(self) -> discord.Embed:
        total_votes = len(self.votes)
        
        # Calculate vote counts per option
        counts = [0] * len(self.options)
        for val in self.votes.values():
            counts[val] += 1

        embed = discord.Embed(
            title=f"📊 Poll: {self.question}",
            description=f"Total Votes: **{total_votes}**\n\n",
            color=discord.Color.blurple()
        )

        def progress_bar(percent: float, size: int = 10) -> str:
            filled = round(percent / 100 * size) if percent > 0 else 0
            return f"`{'█' * filled}{'░' * (size - filled)}`"

        for idx, option in enumerate(self.options):
            cnt = counts[idx]
            pct = (cnt / total_votes * 100) if total_votes > 0 else 0.0
            embed.add_field(
                name=f"{idx + 1}️⃣ {option}",
                value=f"{progress_bar(pct)} {pct:.1f}% ({cnt} votes)",
                inline=False
            )

        embed.set_footer(text="Click a button below to cast/change your vote. Polls are anonymous.")
        return embed


class Utility(commands.Cog):
    """🛠️ Handy server utilities and interactive tools."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Server Info ──────────────────────────────────────────────────────────
    def _get_serverinfo_embed(self, guild: discord.Guild) -> discord.Embed:
        humans = sum(1 for m in guild.members if not m.bot)
        bots = guild.member_count - humans
        
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        
        embed = discord.Embed(
            title=f"🏰 Server Information: {guild.name}",
            color=discord.Color.gold()
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        if guild.banner:
            embed.set_image(url=guild.banner.url)

        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="Server ID", value=f"`{guild.id}`", inline=True)
        embed.add_field(name="Created At", value=discord.utils.format_dt(guild.created_at, 'D'), inline=True)
        
        embed.add_field(name="👥 Members", value=f"• Total: **{guild.member_count}**\n• Humans: **{humans}**\n• Bots: **{bots}**", inline=True)
        embed.add_field(name="📁 Channels", value=f"• Text: **{text_channels}**\n• Voice: **{voice_channels}**\n• Categories: **{categories}**", inline=True)
        embed.add_field(name="🎭 Roles & Emojis", value=f"• Roles: **{len(guild.roles)}**\n• Emojis: **{len(guild.emojis)}**", inline=True)
        
        embed.add_field(name="🛡️ Verification Level", value=str(guild.verification_level).capitalize(), inline=True)
        embed.add_field(name="🔮 Boost Tier", value=f"Tier {guild.premium_tier} ({guild.premium_subscription_count} Boosts)", inline=True)
        
        embed.set_footer(text=f"Requested by the command user")
        return embed

    @commands.command(name="serverinfo", aliases=["si"], help="Get detailed stats about this server.")
    @commands.guild_only()
    async def serverinfo_prefix(self, ctx: commands.Context):
        embed = self._get_serverinfo_embed(ctx.guild)
        await ctx.send(embed=embed)

    @app_commands.command(name="serverinfo", description="Get detailed stats about this server")
    @app_commands.guild_only()
    async def serverinfo_slash(self, interaction: discord.Interaction):
        embed = self._get_serverinfo_embed(interaction.guild)
        await interaction.response.send_message(embed=embed)

    # ── User Info ───────────────────────────────────────────────────────────
    def _get_userinfo_embed(self, member: discord.Member) -> discord.Embed:
        roles = [r.mention for r in member.roles if r != member.guild.default_role]
        roles_str = ", ".join(roles) if roles else "None"
        if len(roles_str) > 1024:
            roles_str = f"{len(roles)} roles"
            
        key_perms = []
        perms = member.guild_permissions
        if perms.administrator:
            key_perms.append("Administrator")
        if perms.manage_guild:
            key_perms.append("Manage Server")
        if perms.manage_channels:
            key_perms.append("Manage Channels")
        if perms.manage_roles:
            key_perms.append("Manage Roles")
        if perms.manage_messages:
            key_perms.append("Manage Messages")
        if perms.kick_members:
            key_perms.append("Kick Members")
        if perms.ban_members:
            key_perms.append("Ban Members")
        if perms.mention_everyone:
            key_perms.append("Mention Everyone")
        
        perms_str = ", ".join(key_perms) if key_perms else "Standard Member"

        embed = discord.Embed(
            title=f"👤 User Information: {member.display_name}",
            color=member.color
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        embed.add_field(name="Username", value=f"{member.name} ({member.mention})", inline=True)
        embed.add_field(name="User ID", value=f"`{member.id}`", inline=True)
        embed.add_field(name="Bot Account?", value="Yes 🤖" if member.bot else "No 👤", inline=True)
        
        embed.add_field(name="Joined Server", value=discord.utils.format_dt(member.joined_at, 'f') if member.joined_at else "Unknown", inline=True)
        embed.add_field(name="Joined Discord", value=discord.utils.format_dt(member.created_at, 'f'), inline=True)
        
        embed.add_field(name="🛡️ Key Permissions", value=perms_str, inline=False)
        embed.add_field(name="🎭 Roles", value=roles_str, inline=False)
        return embed

    @commands.command(name="userinfo", aliases=["ui", "whois"], help="Get info about a guild member. Usage: >userinfo [@member]")
    @commands.guild_only()
    async def userinfo_prefix(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        target = member or ctx.author
        embed = self._get_userinfo_embed(target)
        await ctx.send(embed=embed)

    @app_commands.command(name="userinfo", description="Get info about a server member")
    @app_commands.guild_only()
    @app_commands.describe(member="Select a member (leave blank for yourself)")
    async def userinfo_slash(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        target = member or interaction.user
        embed = self._get_userinfo_embed(target)
        await interaction.response.send_message(embed=embed)

    # ── Interactive Poll ─────────────────────────────────────────────────────
    @commands.command(name="poll", help="Create an interactive poll. Format: >poll \"Question?\" Option1, Option2, Option3...")
    @commands.guild_only()
    async def poll_prefix(self, ctx: commands.Context, question: str, *, options_str: str):
        options = [o.strip() for o in options_str.split(",") if o.strip()]
        if len(options) < 2 or len(options) > 5:
            await ctx.send("❌ Polls must have between 2 and 5 options, separated by commas.")
            return

        view = PollView(question, options)
        embed = view._build_embed()
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name="poll", description="Create an interactive multiple choice poll")
    @app_commands.guild_only()
    @app_commands.describe(
        question="The question to vote on",
        options="Comma-separated options (2 to 5 options, e.g. Yes, No, Maybe)"
    )
    async def poll_slash(self, interaction: discord.Interaction, question: str, options: str):
        opt_list = [o.strip() for o in options.split(",") if o.strip()]
        if len(opt_list) < 2 or len(opt_list) > 5:
            await interaction.response.send_message(
                "❌ Polls must have between 2 and 5 options, separated by commas.",
                ephemeral=True
            )
            return

        view = PollView(question, opt_list)
        embed = view._build_embed()
        await interaction.response.send_message(embed=embed, view=view)

    # ── Avatar viewer ──────────────────────────────────────────────────────────
    @commands.command(name="avatar", aliases=["av", "pfp"], help="Get a user's high-resolution avatar. Usage: >avatar [@member]")
    async def avatar_prefix(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        target = member or ctx.author
        embed = discord.Embed(
            title=f"🖼️ Avatar of {target.display_name}",
            color=target.color
        )
        embed.set_image(url=target.display_avatar.url)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @app_commands.command(name="avatar", description="Get a user's high-resolution avatar")
    @app_commands.describe(member="Select a member (leave blank for yourself)")
    async def avatar_slash(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        target = member or interaction.user
        embed = discord.Embed(
            title=f"🖼️ Avatar of {target.display_name}",
            color=target.color
        )
        embed.set_image(url=target.display_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))
