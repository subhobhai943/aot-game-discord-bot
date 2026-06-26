"""Survey Corps, Garrison, and Military Police Regiment system cog.

This system links self-assignable Discord roles to the RPG system, granting 
unique combat stat passive buffs and welcoming newcomers.
"""
from __future__ import annotations
import os
import json
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from utils.game_state import GameState

CONFIG_FILE = "data/regiment_config.json"

REGIMENTS_INFO = {
    "Survey Corps": {
        "emoji": "⚔️",
        "description": "The branch of the Military that fights Titans outside the walls. Bold, daring, and dedicated to the freedom of humanity.",
        "buff": "⚔️ **Wings of Freedom:** +15% Damage (ATK) in all battles.",
        "color": 0x3498db,  # Blue
    },
    "Garrison": {
        "emoji": "🛡️",
        "description": "The branch that guards the walls and maintains order within the districts. Sturdy, reliable, and defensive.",
        "buff": "🛡️ **Wall Rose Shield:** +20% HP (Max HP) in all battles.",
        "color": 0xe74c3c,  # Red
    },
    "Military Police": {
        "emoji": "🦄",
        "description": "The prestigious branch serving the Royal Family and inner wall districts. Wealthy, privileged, and secure.",
        "buff": "🦄 **Unicorn Privilege:** +20% Coins from all combat victories.",
        "color": 0x2ecc71,  # Green
    },
    "Cadet Corps": {
        "emoji": "🔰",
        "description": "The training branch for recruits. Eager to learn and train before enlisting in their final regiment.",
        "buff": "🔰 **Cadet Training:** +25% XP from all combat victories.",
        "color": 0xf1c40f,  # Yellow
    }
}


class RegimentButton(discord.ui.Button):
    def __init__(self, regiment_name: str, emoji: str, style: discord.ButtonStyle):
        super().__init__(
            label=f"Enlist: {regiment_name}",
            emoji=emoji,
            style=style,
            custom_id=f"regiment_enlist:{regiment_name}"
        )

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Regiments")
        if not cog:
            await interaction.response.send_message("❌ Regiment system is currently unavailable.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        success, embed, file, welcome_ch_id = await cog.enlist_member_core(interaction.guild, interaction.user, self.label.replace("Enlist: ", "").strip())
        
        if success:
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
            if welcome_ch_id and interaction.guild:
                welcome_ch = interaction.guild.get_channel(int(welcome_ch_id))
                if welcome_ch:
                    choice = self.label.replace("Enlist: ", "").strip()
                    reg_info = REGIMENTS_INFO[choice]
                    public_embed = discord.Embed(
                        title="📢 New Enlistment Alert!",
                        description=(
                            f"Soldier **{interaction.user.mention}** has enlisted in the **{choice}**! "
                            f"May they dedicate their heart to humanity! ⚔️"
                        ),
                        color=reg_info["color"]
                    )
                    await welcome_ch.send(embed=public_embed)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)


class RegimentEnlistView(discord.ui.View):
    def __init__(self, cog: Regiments):
        super().__init__(timeout=None)  # Persistent view
        self.add_item(RegimentButton("Survey Corps", "⚔️", discord.ButtonStyle.primary))
        self.add_item(RegimentButton("Garrison", "🛡️", discord.ButtonStyle.danger))
        self.add_item(RegimentButton("Military Police", "🦄", discord.ButtonStyle.success))
        self.add_item(RegimentButton("Cadet Corps", "🔰", discord.ButtonStyle.secondary))


class Regiments(commands.Cog):
    """⚔️ military Regiments — Choose a branch of service to customize your RPG stats and server roles."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.loop.create_task(self.register_view())

    async def register_view(self):
        await self.bot.wait_until_ready()
        self.bot.add_view(RegimentEnlistView(self))

    def _load_config(self) -> dict:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_config(self, data: dict):
        os.makedirs("data", exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)

    # ── Core enlistment engine ────────────────────────────────────────────────
    async def enlist_member_core(
        self, 
        guild: Optional[discord.Guild], 
        member: discord.Member, 
        target_regiment: str
    ) -> tuple[bool, discord.Embed, Optional[discord.File], Optional[str]]:
        player = await GameState.get_player(str(member.id), member.display_name)
        current = player.regiment
        
        if current == target_regiment:
            embed = discord.Embed(
                description=f"❌ You are already enlisted in the **{target_regiment}**!",
                color=discord.Color.red()
            )
            return False, embed, None, None
            
        fee = 0
        fee_message = ""
        main_regiments = ["Survey Corps", "Garrison", "Military Police"]
        if current in main_regiments and target_regiment in main_regiments:
            fee = 500
            if player.coins < fee:
                embed = discord.Embed(
                    description=f"❌ Transferring regiments requires a fee of **500 coins**! You only have **{player.coins} coins**.",
                    color=discord.Color.red()
                )
                return False, embed, None, None

        if fee > 0:
            player.coins -= fee
            fee_message = f"\n💸 Paid **500 coins** transfer fee."
            
        player.regiment = target_regiment
        await GameState.save_player(player)
        
        role_status = ""
        welcome_announcement = None
        if guild:
            guild_id_str = str(guild.id)
            config = self._load_config()
            guild_config = config.get(guild_id_str, {})
            roles_config = guild_config.get("roles", {})
            
            target_role_id = roles_config.get(target_regiment)
            target_role = None
            if target_role_id:
                target_role = guild.get_role(int(target_role_id))
            else:
                target_role = discord.utils.get(guild.roles, name=target_regiment)
                
            if not target_role:
                role_status = f"\n⚠️ *(Server role for **{target_regiment}** was not configured, so only your RPG stats were updated. Ask an admin to link it)*"
            else:
                try:
                    roles_to_remove = []
                    for reg_name in REGIMENTS_INFO:
                        if reg_name == target_regiment:
                            continue
                        r_id = roles_config.get(reg_name)
                        r_obj = None
                        if r_id:
                            r_obj = guild.get_role(int(r_id))
                        else:
                            r_obj = discord.utils.get(guild.roles, name=reg_name)
                        if r_obj and r_obj in member.roles:
                            roles_to_remove.append(r_obj)
                            
                    if roles_to_remove:
                        await member.remove_roles(*roles_to_remove, reason="Regiment change")
                    await member.add_roles(target_role, reason="Regiment enlistment")
                    role_status = f"\n🏷️ Assigned the **{target_role.name}** server role!"
                except discord.Forbidden:
                    role_status = f"\n⚠️ *(Could not assign server role due to missing bot permissions. Ensure the bot's role is placed ABOVE the regiment roles in Server Settings)*"
                    
            if target_regiment != "Cadet Corps":
                welcome_announcement = guild_config.get("welcome_channel_id")

        reg_info = REGIMENTS_INFO[target_regiment]
        embed = discord.Embed(
            title=f"⚔️ Enlistment Successful!",
            description=(
                f"Congratulations, Soldier! You have joined the **{target_regiment}**!\n\n"
                f"**Branch Details:** {reg_info['description']}\n"
                f"**Active Buff:** {reg_info['buff']}\n"
                f"{fee_message}{role_status}"
            ),
            color=reg_info["color"]
        )
        
        file = None
        if target_regiment == "Survey Corps":
            file = discord.File("assets/Titans/survey_corps.png", filename="survey_corps.png")
            embed.set_thumbnail(url="attachment://survey_corps.png")
            
        return True, embed, file, welcome_announcement

    def _build_gate_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="⚔️ THE REGIMENT ENLISTMENT GATES ⚔️",
            description=(
                "Welcome, Soldier! The survival of humanity rests on your shoulders.\n"
                "Before you can deploy on expeditions, you must choose your branch of service.\n\n"
                "Review the branches below, then click a button to enlist. "
                "Each branch provides unique passive buffs that directly affect your stats in combat!"
            ),
            color=0x2c3e50  # Slate/Dark Blue
        )
        
        for name, info in REGIMENTS_INFO.items():
            if name == "Cadet Corps":
                continue
            embed.add_field(
                name=f"{info['emoji']} {name}",
                value=f"*{info['description']}*\n**Buff:** {info['buff']}",
                inline=False
            )
            
        embed.add_field(
            name="🔰 Cadet Corps",
            value=f"*{REGIMENTS_INFO['Cadet Corps']['description']}*\n**Buff:** {REGIMENTS_INFO['Cadet Corps']['buff']}",
            inline=False
        )
        
        embed.add_field(
            name="💸 Transfer Policy",
            value="Joining the Cadet Corps or choosing your first main regiment is free. Transferring between main regiments (e.g. Survey Corps to Garrison) costs **500 coins**.",
            inline=False
        )
        embed.set_footer(text="Wings of Freedom • Dedicate Your Heart!")
        return embed

    async def _get_info_embed(self, member: discord.Member) -> discord.Embed:
        player = await GameState.get_player(str(member.id), member.display_name)
        reg = player.regiment or "Cadet Corps"
        info = REGIMENTS_INFO.get(reg, REGIMENTS_INFO["Cadet Corps"])
        
        embed = discord.Embed(
            title=f"🎖️ Military Record — {member.display_name}",
            description=f"**Regiment:** {info['emoji']} **{reg}**\n*\"Dedicate your heart!\"*",
            color=info["color"]
        )
        
        embed.add_field(name="Level / Rank", value=f"⭐ Lv.{player.level} ({player.rank})", inline=True)
        embed.add_field(name="Coins", value=f"🪙 {player.coins}", inline=True)
        embed.add_field(name="Wins / Losses", value=f"⚔️ {player.wins}W / {player.losses}L", inline=True)
        embed.add_field(name="Active Buff", value=info["buff"], inline=False)
        
        lab_atk = getattr(player, "lab_atk", 0)
        lab_def = getattr(player, "lab_def", 0)
        lab_spd = getattr(player, "lab_spd", 0)
        lab_hp = getattr(player, "lab_hp", 0)
        
        def_bar = lambda val: f"`{'★' * val}{'☆' * (5 - val)}`"
        lab_summary = (
            f"⚔️ ATK: {def_bar(lab_atk)} (+{lab_atk * 5}% dmg)\n"
            f"🛡️ DEF: {def_bar(lab_def)} (-{lab_def * 5}% dmg incoming)\n"
            f"⚡ SPD: {def_bar(lab_spd)} (+{lab_spd * 5}% dodge chance)\n"
            f"🩸 HP:  {def_bar(lab_hp)} (+{lab_hp * 10}% HP max)"
        )
        embed.add_field(name="🔬 Laboratory Upgrades", value=lab_summary, inline=False)
        
        embed.set_footer(text=f"ID: {member.id}")
        return embed

    async def _get_list_embed(self, guild: Optional[discord.Guild]) -> discord.Embed:
        embed = discord.Embed(
            title="🏰 Server Regiments & Cadet Trainees",
            description="The military forces protecting humanity are divided into three specialized branches.",
            color=0x34495e
        )
        
        all_players = await GameState.all_players()
        counts = {name: 0 for name in REGIMENTS_INFO}
        for p in all_players:
            reg = p.regiment or "Cadet Corps"
            if reg in counts:
                counts[reg] += 1
            else:
                counts["Cadet Corps"] += 1
                
        for name, info in REGIMENTS_INFO.items():
            member_count = counts.get(name, 0)
            embed.add_field(
                name=f"{info['emoji']} {name} ({member_count} soldiers)",
                value=f"*{info['description']}*\n**Buff:** {info['buff']}",
                inline=False
            )
            
        embed.set_footer(text="Wings of Freedom • Report to the enlistment gates to join!")
        return embed

    # ── Onboarding / Welcome Event ──────────────────────────────────────────
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_id_str = str(member.guild.id)
        config = self._load_config()
        guild_config = config.get(guild_id_str, {})
        
        gate_ch_id = guild_config.get("gate_channel_id")
        welcome_ch_id = guild_config.get("welcome_channel_id")
        
        if gate_ch_id:
            gate_ch = member.guild.get_channel(int(gate_ch_id))
            if gate_ch:
                welcome_ch = None
                if welcome_ch_id:
                    welcome_ch = member.guild.get_channel(int(welcome_ch_id))
                if not welcome_ch:
                    welcome_ch = member.guild.system_channel
                    
                if welcome_ch:
                    embed = discord.Embed(
                        title="🔰 A new recruit has arrived!",
                        description=(
                            f"Welcome to the server, {member.mention}! You have been registered as a **Cadet**.\n\n"
                            f"Report to the enlistment gates in {gate_ch.mention} to choose your branch of service and receive your role!"
                        ),
                        color=0xf1c40f
                    )
                    embed.set_footer(text="Wings of Freedom • Tatakae!")
                    await welcome_ch.send(embed=embed)

    # ── Prefix commands ───────────────────────────────────────────────────────
    @commands.group(name="regiment", invoke_without_command=True, help="Regiment system: choose your military branch for combat buffs!")
    async def regiment_group(self, ctx: commands.Context):
        await self.info_prefix(ctx)

    @regiment_group.command(name="join", help="Enlist in a regiment. Usage: >regiment join <Survey Corps|Garrison|Military Police|Cadet Corps>")
    async def join_prefix(self, ctx: commands.Context, *, regiment_choice: str):
        matched = None
        for name in REGIMENTS_INFO:
            if name.lower() == regiment_choice.strip().lower() or regiment_choice.strip().lower() in name.lower():
                matched = name
                break
        if not matched:
            await ctx.send("❌ Unknown regiment choice. Options: `Survey Corps`, `Garrison`, `Military Police`, `Cadet Corps`.")
            return

        success, embed, file, welcome_ch_id = await self.enlist_member_core(ctx.guild, ctx.author, matched)
        
        if success:
            await ctx.message.reply(embed=embed, file=file)
            if welcome_ch_id and ctx.guild:
                welcome_ch = ctx.guild.get_channel(int(welcome_ch_id))
                if welcome_ch:
                    reg_info = REGIMENTS_INFO[matched]
                    public_embed = discord.Embed(
                        title="📢 New Enlistment Alert!",
                        description=(
                            f"Soldier **{ctx.author.mention}** has enlisted in the **{matched}**! "
                            f"May they dedicate their heart to humanity! ⚔️"
                        ),
                        color=reg_info["color"]
                    )
                    await welcome_ch.send(embed=public_embed)
        else:
            await ctx.send(embed=embed)

    @regiment_group.command(name="info", help="View military record for yourself or another soldier. Usage: >regiment info [@member]")
    async def info_prefix(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        target = member or ctx.author
        embed = await self._get_info_embed(target)
        file = None
        player = await GameState.get_player(str(target.id), target.display_name)
        if player.regiment == "Survey Corps":
            file = discord.File("assets/Titans/survey_corps.png", filename="survey_corps.png")
            embed.set_thumbnail(url="attachment://survey_corps.png")
        await ctx.send(embed=embed, file=file)

    @regiment_group.command(name="list", help="List all regiments, their passive buffs, and member counts.")
    async def list_prefix(self, ctx: commands.Context):
        embed = await self._get_list_embed(ctx.guild)
        await ctx.send(embed=embed)

    @regiment_group.command(name="setupgate", help="Send the regiment enlistment gates to this channel (Admin only)")
    @commands.has_permissions(manage_guild=True)
    async def setup_gate_prefix(self, ctx: commands.Context):
        embed = self._build_gate_embed()
        view = RegimentEnlistView(self)
        
        guild_id_str = str(ctx.guild.id)
        config = self._load_config()
        config.setdefault(guild_id_str, {})["gate_channel_id"] = str(ctx.channel.id)
        self._save_config(config)
        
        file = discord.File("assets/Titans/survey_corps.png", filename="survey_corps.png")
        embed.set_thumbnail(url="attachment://survey_corps.png")
        
        await ctx.send(embed=embed, file=file, view=view)

    @regiment_group.command(name="linkrole", help="Link a regiment to a server role. Usage: >regiment linkrole <Survey Corps|Garrison|Military Police|Cadet Corps> <@role>")
    @commands.has_permissions(manage_guild=True)
    async def link_role_prefix(self, ctx: commands.Context, regiment_choice: str, role: discord.Role):
        matched = None
        for name in REGIMENTS_INFO:
            if name.lower() == regiment_choice.strip().lower() or regiment_choice.strip().lower() in name.lower():
                matched = name
                break
        if not matched:
            await ctx.send("❌ Unknown regiment choice. Options: `Survey Corps`, `Garrison`, `Military Police`, `Cadet Corps`.")
            return
            
        guild_id_str = str(ctx.guild.id)
        config = self._load_config()
        config.setdefault(guild_id_str, {}).setdefault("roles", {})
        config[guild_id_str]["roles"][matched] = str(role.id)
        self._save_config(config)
        await ctx.send(f"✅ Success! **{matched}** is now linked to role {role.mention}.")

    @regiment_group.command(name="setchannel", help="Configure welcome or gate channel. Usage: >regiment setchannel <welcome|gate> <#channel>")
    @commands.has_permissions(manage_guild=True)
    async def set_channel_prefix(self, ctx: commands.Context, channel_type: str, channel: discord.TextChannel):
        c_type = channel_type.strip().lower()
        if c_type not in ["welcome", "gate"]:
            await ctx.send("❌ Invalid channel type! Use `welcome` or `gate`.")
            return
            
        guild_id_str = str(ctx.guild.id)
        config = self._load_config()
        guild_config = config.setdefault(guild_id_str, {})
        
        if c_type == "welcome":
            guild_config["welcome_channel_id"] = str(channel.id)
            await ctx.send(f"✅ Success! Welcome alerts will now be sent to {channel.mention}.")
        else:
            guild_config["gate_channel_id"] = str(channel.id)
            await ctx.send(f"✅ Success! Enlistment gates channel configured as {channel.mention}.")
            
        self._save_config(config)

    # ── Slash commands ────────────────────────────────────────────────────────
    @app_commands.command(name="regiment-info", description="View military record for yourself or another soldier")
    @app_commands.describe(member="Member to inspect")
    async def info_slash(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        target = member or interaction.user
        embed = await self._get_info_embed(target)
        file = None
        player = await GameState.get_player(str(target.id), target.display_name)
        if player.regiment == "Survey Corps":
            file = discord.File("assets/Titans/survey_corps.png", filename="survey_corps.png")
            embed.set_thumbnail(url="attachment://survey_corps.png")
        await interaction.response.send_message(embed=embed, file=file)

    @app_commands.command(name="regiment-list", description="List all regiments, their passive buffs, and member counts")
    async def list_slash(self, interaction: discord.Interaction):
        embed = await self._get_list_embed(interaction.guild)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="regiment-join", description="Enlist in a regiment for unique RPG combat buffs")
    @app_commands.describe(choice="The regiment you wish to enlist in")
    @app_commands.choices(choice=[
        app_commands.Choice(name=name, value=name) for name in REGIMENTS_INFO
    ])
    async def join_slash(self, interaction: discord.Interaction, choice: str):
        await interaction.response.defer(ephemeral=True)
        success, embed, file, welcome_ch_id = await self.enlist_member_core(interaction.guild, interaction.user, choice)
        
        if success:
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
            if welcome_ch_id and interaction.guild:
                welcome_ch = interaction.guild.get_channel(int(welcome_ch_id))
                if welcome_ch:
                    reg_info = REGIMENTS_INFO[choice]
                    public_embed = discord.Embed(
                        title="📢 New Enlistment Alert!",
                        description=(
                            f"Soldier **{interaction.user.mention}** has enlisted in the **{choice}**! "
                            f"May they dedicate their heart to humanity! ⚔️"
                        ),
                        color=reg_info["color"]
                    )
                    await welcome_ch.send(embed=public_embed)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="regiment-setup-gate", description="Send the interactive regiment enlistment gates to this channel (Admin only)")
    @app_commands.default_permissions(manage_guild=True)
    async def setup_gate_slash(self, interaction: discord.Interaction):
        embed = self._build_gate_embed()
        view = RegimentEnlistView(self)
        
        guild_id_str = str(interaction.guild_id)
        config = self._load_config()
        config.setdefault(guild_id_str, {})["gate_channel_id"] = str(interaction.channel_id)
        self._save_config(config)
        
        file = discord.File("assets/Titans/survey_corps.png", filename="survey_corps.png")
        embed.set_thumbnail(url="attachment://survey_corps.png")
        
        await interaction.response.send_message("✅ Dispatching the Enlistment Gates...", ephemeral=True)
        await interaction.channel.send(embed=embed, file=file, view=view)

    @app_commands.command(name="regiment-link-role", description="Link a regiment to a Discord role (Admin only)")
    @app_commands.describe(regiment="Which regiment to link", role="The Discord role to assign")
    @app_commands.choices(regiment=[
        app_commands.Choice(name=name, value=name) for name in REGIMENTS_INFO
    ])
    @app_commands.default_permissions(manage_guild=True)
    async def link_role_slash(self, interaction: discord.Interaction, regiment: str, role: discord.Role):
        guild_id_str = str(interaction.guild_id)
        config = self._load_config()
        config.setdefault(guild_id_str, {}).setdefault("roles", {})
        config[guild_id_str]["roles"][regiment] = str(role.id)
        self._save_config(config)
        
        embed = discord.Embed(
            title="⚙️ Role Linked",
            description=f"Success! Enlisting in the **{regiment}** will now assign the role {role.mention}.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="regiment-set-channels", description="Set channels for regiment welcome alerts and enlistment gates (Admin only)")
    @app_commands.describe(
        welcome_channel="Channel where public enlistment announcements are made",
        gate_channel="Channel where new members are directed to enlist"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def set_channels_slash(
        self, 
        interaction: discord.Interaction, 
        welcome_channel: Optional[discord.TextChannel] = None, 
        gate_channel: Optional[discord.TextChannel] = None
    ):
        guild_id_str = str(interaction.guild_id)
        config = self._load_config()
        guild_config = config.setdefault(guild_id_str, {})
        
        msg_parts = []
        if welcome_channel:
            guild_config["welcome_channel_id"] = str(welcome_channel.id)
            msg_parts.append(f"Welcome alerts: {welcome_channel.mention}")
        if gate_channel:
            guild_config["gate_channel_id"] = str(gate_channel.id)
            msg_parts.append(f"Enlistment gates: {gate_channel.mention}")
            
        self._save_config(config)
        
        if not msg_parts:
            await interaction.response.send_message("❌ Please specify at least one channel to configure.", ephemeral=True)
            return
            
        embed = discord.Embed(
            title="⚙️ Channels Configured",
            description=f"Success! Configured channels:\n" + "\n".join(f"• {p}" for p in msg_parts),
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Regiments(bot))
