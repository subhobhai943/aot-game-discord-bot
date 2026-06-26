"""Multiplayer Co-op PvE Titan Raid Cog.

Allows servers to team up and fight high-HP Boss Titans (Colossal, Armored, Beast, Founding).
"""
from __future__ import annotations
import asyncio
import random
from dataclasses import dataclass
from typing import Optional
import discord
from discord.ext import commands
from discord import app_commands
from utils.game_state import (
    GameState, TITAN_STATS, get_titan_image, attach_image,
    RARITY_COLOR, RARITY_EMOJI, SURVEY_CORPS_ICON
)
from utils.gifs import get_gif


BOSS_TEMPLATES = {
    "Colossal Titan": {
        "base_hp": 1200,
        "hp_per_player": 400,
        "atk": 75,
        "def": 60,
        "color": discord.Color.red(),
        "gif_key": "colossal",
        "description": "The giant that broke Wall Maria. Emits devastating steam blasts that burn everyone!",
        "aoe_name": "Steam Explosion",
        "aoe_desc": "unleashes a superheated wave of steam, boiling the entire vanguard!",
        "single_name": "Colossal Sweep",
        "single_desc": "sweeps its gargantuan arm across the battlefield at"
    },
    "Armored Titan": {
        "base_hp": 900,
        "hp_per_player": 350,
        "atk": 65,
        "def": 85,  # Reduces Slash damage by 30%
        "color": discord.Color.gold(),
        "gif_key": "armored",
        "description": "Heavily plated with hardened skin. Incredible defense and devastating charging tackles!",
        "aoe_name": "Earthquake Stomp",
        "aoe_desc": "stomps the ground, shattering rooftops and throwing everyone off balance!",
        "single_name": "Armored Charge",
        "single_desc": "sprints forward and tackles head-on, smashing into"
    },
    "Beast Titan": {
        "base_hp": 1000,
        "hp_per_player": 380,
        "atk": 80,
        "def": 50,
        "color": discord.Color.from_rgb(139, 69, 19),
        "gif_key": "wall_break",
        "description": "A fur-covered giant throwing boulders with high velocity. Extremely lethal single targets!",
        "aoe_name": "Boulder Rain",
        "aoe_desc": "pulverizes a boulder and showers the entire battlefield in jagged rock shrapnel!",
        "single_name": "Targeted Pitch",
        "single_desc": "aims and throws a high-speed boulder directly at"
    },
    "Founding Titan": {
        "base_hp": 1400,
        "hp_per_player": 450,
        "atk": 85,
        "def": 70,
        "color": discord.Color.purple(),
        "gif_key": "founding",
        "description": "The progenitor of all Titans. Channels ancient cries to summon Pure Titans and stun scouts!",
        "aoe_name": "Rumbling Tremor",
        "aoe_desc": "triggers a miniature rumbling wave, crushing the surrounding area!",
        "single_name": "Commanding Screech",
        "single_desc": "screams an ancient command, summoning a Pure Titan to bite down on"
    }
}


@dataclass
class RaidPlayer:
    user_id: str
    username: str
    mention: str
    hp: int = 300
    max_hp: int = 300
    damage_dealt: int = 0
    move: Optional[str] = None
    defense_buff: bool = False
    evaded_buff: bool = False


class RaidSession:
    def __init__(self, guild_id: int, channel: discord.TextChannel, creator: discord.User | discord.Member):
        self.guild_id = guild_id
        self.channel = channel
        self.creator = creator
        self.players: dict[str, RaidPlayer] = {}
        
        # Select random boss
        self.boss_type = random.choice(list(BOSS_TEMPLATES.keys()))
        self.boss_meta = BOSS_TEMPLATES[self.boss_type]
        self.boss_hp = self.boss_meta["base_hp"]
        self.boss_max_hp = self.boss_meta["base_hp"]
        
        self.round_num = 1
        self.active = True
        self.lobby_open = True
        self.combat_log: list[str] = []
        self.lobby_message: Optional[discord.Message] = None
        self.combat_message: Optional[discord.Message] = None


# Active raids cache: guild_id -> RaidSession
_active_raids: dict[int, RaidSession] = {}


class RaidLobbyView(discord.ui.View):
    """View handling the recruitment lobby phase of the Raid."""

    def __init__(self, session: RaidSession):
        super().__init__(timeout=45)
        self.session = session

    async def on_timeout(self):
        self.stop()
        if self.session.lobby_open:
            self.session.lobby_open = False
            await self._start_combat()

    @discord.ui.button(label="Join Vanguard 🗡️", style=discord.ButtonStyle.danger)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        if uid in self.session.players:
            await interaction.response.send_message("❌ You have already joined the Vanguard!", ephemeral=True)
            return

        # Add player
        self.session.players[uid] = RaidPlayer(
            user_id=uid,
            username=interaction.user.display_name,
            mention=interaction.user.mention
        )
        # Scale Boss HP
        self.session.boss_max_hp = self.session.boss_meta["base_hp"] + (len(self.session.players) * self.session.boss_meta["hp_per_player"])
        self.session.boss_hp = self.session.boss_max_hp

        await interaction.response.send_message("⚔️ You have joined the Vanguard! Prepare to fight!", ephemeral=True)
        await self._update_lobby_message()

    @discord.ui.button(label="Start Battle 🏁", style=discord.ButtonStyle.success)
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.creator.id:
            await interaction.response.send_message("❌ Only the raid creator can force-start the battle early!", ephemeral=True)
            return

        if len(self.session.players) == 0:
            await interaction.response.send_message("❌ At least one soldier must join the Vanguard before starting!", ephemeral=True)
            return

        self.session.lobby_open = False
        self.stop()
        await interaction.response.defer()
        await self._start_combat()

    async def _update_lobby_message(self):
        embed = self.session.lobby_message.embeds[0]
        vanguard_list = "\n".join([f"• {p.username}" for p in self.session.players.values()]) or "*Waiting for recruits...*"
        embed.set_field_at(
            0,
            name=f"👥 Vanguard Soldiers ({len(self.session.players)}):",
            value=vanguard_list,
            inline=False
        )
        embed.set_field_at(
            1,
            name="👹 Raid Boss Details:",
            value=(
                f"**Boss:** {self.session.boss_type}\n"
                f"**Estimated Health:** `{self.session.boss_hp} HP`\n"
                f"**Speciality:** {self.session.boss_meta['description']}"
            ),
            inline=False
        )
        await self.session.lobby_message.edit(embed=embed, view=self)

    async def _start_combat(self):
        # Disable view buttons
        for child in self.children:
            child.disabled = True
        await self.session.lobby_message.edit(view=self)

        if len(self.session.players) == 0:
            embed = discord.Embed(
                title="📯 Raid Cancelled",
                description="No scouts joined the Vanguard. Erwin has ordered a tactical retreat.",
                color=discord.Color.greyple()
            )
            await self.session.channel.send(embed=embed)
            _active_raids.pop(self.session.guild_id, None)
            return

        # Start combat loop
        cog = self.session.channel.guild.get_member(self.session.creator.id).guild.me.guild.get_cog("Raid")
        if cog:
            self.session.lobby_open = False
            await cog.run_combat_loop(self.session)


class CombatActionView(discord.ui.View):
    """View presented to players every round to select their action."""

    def __init__(self, session: RaidSession, bot: commands.Bot):
        super().__init__(timeout=25)
        self.session = session
        self.bot = bot
        self.locked_in = set()

    async def on_timeout(self):
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        uid = str(interaction.user.id)
        if uid not in self.session.players:
            await interaction.response.send_message("❌ You are not part of the Vanguard for this Raid!", ephemeral=True)
            return False
        
        player = self.session.players[uid]
        if player.hp <= 0:
            await interaction.response.send_message("💀 You have fallen in battle and cannot take any more moves!", ephemeral=True)
            return False

        if uid in self.locked_in:
            await interaction.response.send_message("⏳ You have already locked in your move for this round!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Slash ⚔️", style=discord.ButtonStyle.danger)
    async def slash_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        self.session.players[uid].move = "slash"
        self.locked_in.add(uid)
        await interaction.response.send_message("⚔️ Locked in: **Slash**!", ephemeral=True)
        await self._check_round_readiness()

    @discord.ui.button(label="T-Spear 💥", style=discord.ButtonStyle.primary)
    async def tspear_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        self.session.players[uid].move = "tspear"
        self.locked_in.add(uid)
        await interaction.response.send_message("💥 Locked in: **Thunder Spear**!", ephemeral=True)
        await self._check_round_readiness()

    @discord.ui.button(label="ODM Dodge 🚀", style=discord.ButtonStyle.success)
    async def dodge_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        self.session.players[uid].move = "dodge"
        self.locked_in.add(uid)
        await interaction.response.send_message("🚀 Locked in: **ODM Evasion**!", ephemeral=True)
        await self._check_round_readiness()

    @discord.ui.button(label="Iron Guard 🛡️", style=discord.ButtonStyle.secondary)
    async def defend_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        self.session.players[uid].move = "defend"
        self.locked_in.add(uid)
        await interaction.response.send_message("🛡️ Locked in: **Iron Guard**!", ephemeral=True)
        await self._check_round_readiness()

    async def _check_round_readiness(self):
        # Living players
        living = [uid for uid, p in self.session.players.items() if p.hp > 0]
        if all(uid in self.locked_in for uid in living):
            self.stop()


class Raid(commands.Cog):
    """⚔️ Multiplayer Co-op PvE Titan Raid system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _hp_bar(self, hp: int, max_hp: int, n: int = 15) -> str:
        filled = int(max(0, hp / max(max_hp, 1)) * n)
        return "🔴" * filled + "⚫" * (n - filled)

    # ── Command ───────────────────────────────────────────────────────────────
    @commands.command(name="raid", help="Initiate a multiplayer co-op PvE Titan Raid boss fight!")
    async def raid_prefix(self, ctx: commands.Context):
        await self._initiate_raid(ctx.guild.id, ctx.channel, ctx.author)

    @app_commands.command(name="raid", description="Initiate a multiplayer co-op PvE Titan Raid boss fight")
    async def raid_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._initiate_raid(interaction.guild_id, interaction.channel, interaction.user)
        await interaction.followup.send("📯 Raid alert sounded!", ephemeral=True)

    async def _initiate_raid(self, guild_id: int, channel: discord.TextChannel, creator: discord.User | discord.Member):
        if guild_id in _active_raids:
            await channel.send("❌ A raid is already active in this server! Finish the current battle first.")
            return

        session = RaidSession(guild_id, channel, creator)
        _active_raids[guild_id] = session

        embed = discord.Embed(
            title=f"⚠️ RED ALERT: {session.boss_type} RAID!",
            description=(
                f"Commander Erwin has ordered a raid on the **{session.boss_type}** outside the wall!\n"
                f"Recruitment lobby is open. Prepare your ODM gears, soldiers!\n\n"
                f"**Raid Creator:** {creator.mention}\n"
                f"⏳ Battle commences in **45 seconds**."
            ),
            color=session.boss_meta["color"]
        )
        embed.add_field(name="👥 Vanguard Soldiers (0):", value="*Waiting for recruits...*", inline=False)
        embed.add_field(
            name="👹 Raid Boss Details:",
            value=(
                f"**Boss:** {session.boss_type}\n"
                f"**Estimated Health:** `{session.boss_hp} HP`\n"
                f"**Speciality:** {session.boss_meta['description']}"
            ),
            inline=False
        )
        
        file = attach_image(embed, get_titan_image(session.boss_type))
        view = RaidLobbyView(session)
        
        if file:
            session.lobby_message = await channel.send(embed=embed, file=file, view=view)
        else:
            session.lobby_message = await channel.send(embed=embed, view=view)

    # ── Combat Loop Resolver ──────────────────────────────────────────────────
    async def run_combat_loop(self, session: RaidSession):
        await session.channel.send(f"📢 **Vanguard deployed!** Engaging the **{session.boss_type}** now!")
        await asyncio.sleep(2)

        while session.boss_hp > 0 and any(p.hp > 0 for p in session.players.values()):
            # 1. Reset round buffs
            for p in session.players.values():
                p.move = None
                p.defense_buff = False
                p.evaded_buff = False

            # 2. Build Round embed
            round_embed = discord.Embed(
                title=f"🛡️ {session.boss_type} Raid — Round {session.round_num}",
                description=f"Choose your move using the buttons below within **25 seconds**!",
                color=session.boss_meta["color"]
            )
            # HP states
            living_p = [p for p in session.players.values() if p.hp > 0]
            team_hp_sum = sum(p.hp for p in living_p)
            team_max_sum = sum(p.max_hp for p in living_p)
            
            round_embed.add_field(
                name=f"👹 {session.boss_type} HP:",
                value=f"{self._hp_bar(session.boss_hp, session.boss_max_hp)} `{session.boss_hp}/{session.boss_max_hp} HP`",
                inline=False
            )
            round_embed.add_field(
                name="👥 Vanguard Team HP:",
                value=f"{self._hp_bar(team_hp_sum, team_max_sum)} `{team_hp_sum}/{team_max_sum} HP` ({len(living_p)} alive)",
                inline=False
            )

            # Player List Status
            status_lines = []
            for p in session.players.values():
                hp_indicator = f"🟩 {p.hp}/{p.max_hp}" if p.hp > 0 else "💀 DEAD"
                status_lines.append(f"• **{p.username}**: {hp_indicator} | Dealt: `{p.damage_dealt} DMG`")
            
            round_embed.add_field(name="📊 Soldier Status:", value="\n".join(status_lines), inline=False)

            view = CombatActionView(session, self.bot)
            action_msg = await session.channel.send(embed=round_embed, view=view)
            
            # Wait for turn input
            await view.wait()
            
            # Delete selection embed to keep chat clean
            try:
                await action_msg.delete()
            except Exception:
                pass

            # Auto-assign moves for AFK players
            for p in session.players.values():
                if p.hp > 0 and p.move is None:
                    p.move = random.choice(["slash", "defend"])

            # 3. Resolve Attacks
            round_log = []
            total_damage_this_round = 0
            
            # Apply defense buffs and player attacks
            for p in session.players.values():
                if p.hp <= 0:
                    continue

                if p.move == "defend":
                    p.defense_buff = True
                    round_log.append(f"🛡️ **{p.username}** took a defensive stance, raising their shields!")
                
                elif p.move == "dodge":
                    p.evaded_buff = True
                    dmg = random.randint(30, 50)
                    if session.boss_type == "Armored Titan":
                        dmg = int(dmg * 0.7)  # Armored Boss defense reduction
                    p.damage_dealt += dmg
                    total_damage_this_round += dmg
                    session.boss_hp -= dmg
                    round_log.append(f"🚀 **{p.username}** swing-dashed with ODM gear dealing **{dmg} DMG**!")
                
                elif p.move == "tspear":
                    if random.random() < 0.25:
                        # Miss & Backfire
                        backfire_dmg = random.randint(30, 50)
                        p.hp = max(0, p.hp - backfire_dmg)
                        round_log.append(f"❌ **{p.username}** missed their Thunder Spear and took **{backfire_dmg} backfire DMG**!")
                    else:
                        dmg = random.randint(120, 180)
                        if session.boss_type == "Armored Titan":
                            dmg = int(dmg * 0.9)  # Less reduction for piercing spear
                        p.damage_dealt += dmg
                        total_damage_this_round += dmg
                        session.boss_hp -= dmg
                        round_log.append(f"💥 **{p.username}** fired a Thunder Spear dealing **{dmg} DMG**!")
                
                else:  # slash
                    dmg = random.randint(60, 90)
                    if session.boss_type == "Armored Titan":
                        dmg = int(dmg * 0.7)
                    p.damage_dealt += dmg
                    total_damage_this_round += dmg
                    session.boss_hp -= dmg
                    round_log.append(f"⚔️ **{p.username}** slashed the nape dealing **{dmg} DMG**!")

            # 4. Resolve Boss Turn (if not dead)
            if session.boss_hp <= 0:
                session.boss_hp = 0
            else:
                # Titan attack selector
                is_aoe = random.random() < 0.5
                boss_atk = session.boss_meta["atk"]

                if is_aoe:
                    round_log.append(f"\n👹 **{session.boss_type}** {session.boss_meta['aoe_name']}! {session.boss_meta['aoe_desc']}")
                    for p in session.players.values():
                        if p.hp <= 0:
                            continue
                        dmg = random.randint(boss_atk - 15, boss_atk + 10)
                        if p.defense_buff:
                            dmg = int(dmg * 0.2)
                            round_log.append(f"└ **{p.username}** blocked most of it! Takes `{dmg} DMG`.")
                        else:
                            round_log.append(f"└ **{p.username}** takes `{dmg} DMG`.")
                        p.hp = max(0, p.hp - dmg)
                else:
                    # Single Target
                    living = [p for p in session.players.values() if p.hp > 0]
                    target = random.choice(living)
                    round_log.append(f"\n👹 **{session.boss_type}** uses {session.boss_meta['single_name']}! {session.boss_meta['single_desc']} **{target.username}**!")
                    
                    if target.evaded_buff and random.random() < 0.5:
                        round_log.append(f"└ 💫 **{target.username}** swiftly dodged the attack with ODM gear!")
                    else:
                        dmg = random.randint(boss_atk + 10, boss_atk + 40)
                        if target.defense_buff:
                            dmg = int(dmg * 0.2)
                            round_log.append(f"└ **{target.username}** blocks the impact! Takes `{dmg} DMG`.")
                        else:
                            round_log.append(f"└ **{target.username}** takes a direct hit for `{dmg} DMG`!")
                        target.hp = max(0, target.hp - dmg)

            # 5. Send Round Result Embed
            result_embed = discord.Embed(
                title=f"🎬 Round {session.round_num} Resolution",
                description="\n".join(round_log),
                color=session.boss_meta["color"]
            )
            result_embed.add_field(
                name=f"👹 {session.boss_type} HP Status:",
                value=f"{self._hp_bar(session.boss_hp, session.boss_max_hp)} `{session.boss_hp}/{session.boss_max_hp} HP`",
                inline=False
            )
            
            gif_url = await get_gif(session.boss_meta["gif_key"])
            if gif_url:
                result_embed.set_image(url=gif_url)
            
            await session.channel.send(embed=result_embed)
            session.round_num += 1
            await asyncio.sleep(4)

        # ── Combat Over Resolver ──────────────────────────────────────────────
        await self._resolve_raid_end(session)

    async def _resolve_raid_end(self, session: RaidSession):
        _active_raids.pop(session.guild_id, None)
        
        # Did scouts win?
        victory = session.boss_hp <= 0
        
        embed = discord.Embed(
            title="📯 RAID BATTLE RESOLUTION",
            color=discord.Color.green() if victory else discord.Color.red()
        )
        
        gif_key = "freedom" if victory else "cry"
        gif_url = await get_gif(gif_key)
        if gif_url:
            embed.set_image(url=gif_url)

        if victory:
            # MVP calculation
            mvp_player = max(session.players.values(), key=lambda p: p.damage_dealt)
            embed.description = (
                f"🎉 **VICTORY FOR HUMANITY!**\n"
                f"The **{session.boss_type}** has been driven back!\n\n"
                f"👑 **Raid MVP:** {mvp_player.mention} with `{mvp_player.damage_dealt} DMG`!\n"
                f"All vanguard survivors and participants receive their bounty."
            )
            
            # Rewards distribution
            reward_coins = 200
            reward_xp = 300
            
            reward_summary = []
            for p in session.players.values():
                player = await GameState.get_player(p.user_id, p.username)
                player.coins += reward_coins
                # MVP gets bonus
                xp_gained = reward_xp
                coins_gained = reward_coins
                if p.user_id == mvp_player.user_id:
                    xp_gained += 100
                    coins_gained += 50
                    player.coins += 50

                leveled_up = player.add_xp(xp_gained)
                await GameState.save_player(player)
                
                status_str = f"💰 +{coins_gained} coins | 📈 +{xp_gained} XP"
                if leveled_up:
                    status_str += f" | 🎉 **Level {player.level}!**"
                reward_summary.append(f"• **{p.username}**: {status_str}")
                
            embed.add_field(name="🎁 Vanguard Rewards:", value="\n".join(reward_summary), inline=False)
        else:
            embed.description = (
                f"💀 **VANGUARD WIPED OUT!**\n"
                f"The **{session.boss_type}** overwhelmed the defenses. Commander Erwin ordered a full retreat.\n\n"
                f"Consolation supplies have been distributed to the troops."
            )
            
            reward_coins = 30
            reward_xp = 50
            
            reward_summary = []
            for p in session.players.values():
                player = await GameState.get_player(p.user_id, p.username)
                player.coins += reward_coins
                leveled_up = player.add_xp(reward_xp)
                await GameState.save_player(player)
                
                status_str = f"💰 +{reward_coins} coins | 📈 +{reward_xp} XP"
                if leveled_up:
                    status_str += f" | 🎉 **Level {player.level}!**"
                reward_summary.append(f"• **{p.username}**: {status_str}")
                
            embed.add_field(name="🎁 Consolation Rewards:", value="\n".join(reward_summary), inline=False)

        await session.channel.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Raid(bot))
