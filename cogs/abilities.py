"""Character abilities, titan transformations, and gear upgrades."""
import discord
from discord.ext import commands
from discord import app_commands
from utils.game_state import GameState, CHARACTERS, TITANS
from utils.gifs import get_gif
import random

class Abilities(commands.Cog):
    """Character abilities and special operations."""

    def __init__(self, bot):
        self.bot = bot

    # ── Character Ability Command ────────────────────────────────────────────

    @app_commands.command(name="ability", description="Use your scout's special ability!")
    async def use_ability(self, interaction: discord.Interaction):
        """Activate your chosen scout's signature ability."""
        player = GameState.get_player(str(interaction.user.id), interaction.user.display_name)
        
        abilities_db = {
            "Levi Ackerman": {
                "name": "Blade Storm",
                "emoji": "⚔️",
                "color": discord.Color.teal(),
                "description": "Unleashes rapid, precise strikes that deal massive damage to Titans. No Titan can withstand Levi's onslaught.",
                "effect": "Deals 150% damage and ignores Titan armor",
                "query": "levi ackerman ultra fast attack",
            },
            "Mikasa Ackerman": {
                "name": "Ackerman Awakening",
                "emoji": "💥",
                "color": discord.Color.red(),
                "description": "Taps into her awakened power for incredible speed and strength. A perfect defense that can cut down any foe.",
                "effect": "Perfect dodge + counterattack (200% damage)",
                "query": "mikasa ackerman power awaken",
            },
            "Eren Yeager": {
                "name": "Rumbling Fury",
                "emoji": "⚡",
                "color": discord.Color.dark_orange(),
                "description": "Channels his determination and Titan power into a devastating assault. The will to fight beyond limits!",
                "effect": "Massive damage + stuns Titan for 1 turn",
                "query": "eren yeager titan power",
            },
            "Armin Arlert": {
                "name": "Colossal Might",
                "emoji": "💥",
                "color": discord.Color.orange(),
                "description": "Transforms into the Colossal Titan, creating an explosive force that obliterates everything in range.",
                "effect": "Area damage to nearby Titans (300% damage)",
                "query": "colossal titan explosion transformation",
            },
            "Hange Zoë": {
                "name": "Titan Research",
                "emoji": "🔬",
                "color": discord.Color.purple(),
                "description": "Analyzes Titan weaknesses and exploits them for critical strikes. Knowledge is power!",
                "effect": "Reveals Titan weak point for +50% damage next turn",
                "query": "hange zoe titan research",
            },
            "Erwin Smith": {
                "name": "Commander's Gambit",
                "emoji": "🗡️",
                "color": discord.Color.dark_gold(),
                "description": "Leads an inspiring charge that boosts all allies' morale and combat effectiveness. Long live the Scouts!",
                "effect": "Boosts team damage by 50% for 2 turns",
                "query": "erwin smith commander charge",
            },
            "Reiner Braun": {
                "name": "Armored Shield",
                "emoji": "🛡️",
                "color": discord.Color.grey(),
                "description": "Hardens his Titan's armor to near impenetrable levels, protecting all allies from harm.",
                "effect": "Reduces all damage taken by 80% for 2 turns",
                "query": "armored titan hardening",
            },
            "Annie Leonhart": {
                "name": "Crystal Fortress",
                "emoji": "💎",
                "color": discord.Color.blue(),
                "description": "Encases herself in unbreakable crystal, making her invulnerable while planning the perfect counterstrike.",
                "effect": "Becomes invulnerable and gains 2x damage next turn",
                "query": "annie leonhart crystal hardening",
            },
            "Bertholdt Hoover": {
                "name": "Explosive Heat",
                "emoji": "🔥",
                "color": discord.Color.red(),
                "description": "Unleashes the scorching heat of the Colossal Titan, burning away all opposition in a wave of destruction.",
                "effect": "Massive burn damage over time to all enemies",
                "query": "colossal titan steam explosion",
            },
        }
        
        ability = abilities_db.get(player.scout_name, abilities_db["Eren Yeager"])
        
        embed = discord.Embed(
            title=f"{ability['emoji']} {ability['name']}",
            description=f"**{player.scout_name}** activates their special ability!\n\n{ability['description']}\n\n**Effect:** {ability['effect']}",
            color=ability["color"]
        )
        
        gif_url = await get_gif(ability["name"].lower().replace(' ', '_'), ability["query"])
        if gif_url:
            embed.set_image(url=gif_url)
        
        embed.set_footer(text="🪶 Scout abilities are the key to humanity's survival!")
        
        # Grant XP for using ability
        player.add_xp(15)
        GameState.save_player(player)
        
        await interaction.response.send_message(embed=embed)

    # ── Titan Transformation Simulator ───────────────────────────────────────

    @app_commands.command(
        name="transform",
        description="Simulate transforming into a Titan (or becoming one)!")
    @app_commands.describe(titan="Which Titan to transform into")
    @app_commands.choices(titan=[
        app_commands.Choice(name="Attack Titan", value="attack"),
        app_commands.Choice(name="Founding Titan", value="founding"),
        app_commands.Choice(name="Colossal Titan", value="colossal"),
        app_commands.Choice(name="Armored Titan", value="armored"),
        app_commands.Choice(name="Beast Titan", value="beast"),
        app_commands.Choice(name="Female Titan", value="female"),
        app_commands.Choice(name="Jaw Titan", value="jaw"),
        app_commands.Choice(name="Cart Titan", value="cart"),
        app_commands.Choice(name="War Hammer Titan", value="warhammer"),
    ])
    async def transform(self, interaction: discord.Interaction, titan: app_commands.Choice[str]):
        """Experience what it's like to become a Titan!"""
        
        titan_data = {
            "attack": {
                "name": "Attack Titan",
                "emoji": "⚔️",
                "color": discord.Color.red(),
                "height": "15m",
                "desc": "The Titan that fights for freedom across generations! Eren's unstoppable force!",
                "ability": "Can see future inheritors' memories",
            },
            "founding": {
                "name": "Founding Titan",
                "emoji": "👑",
                "color": discord.Color.gold(),
                "height": "13m",
                "desc": "The legendary Titan with absolute power over all Subjects of Ymir!",
                "ability": "Can control all Titans and alter memories",
            },
            "colossal": {
                "name": "Colossal Titan",
                "emoji": "💥",
                "color": discord.Color.orange(),
                "height": "60m",
                "desc": "The largest and most destructive Titan! Creates explosions upon transformation!",
                "ability": "Can emit steam at will for defense/offense",
            },
            "armored": {
                "name": "Armored Titan",
                "emoji": "🛡️",
                "color": discord.Color.grey(),
                "height": "15m",
                "desc": "Covered in hardened plates, this Titan is a living fortress!",
                "ability": "Can harden entire body for near invulnerability",
            },
            "beast": {
                "name": "Beast Titan",
                "emoji": "🦍",
                "color": discord.Color.dark_green(),
                "height": "17m",
                "desc": "A Titan with animal features and unmatched throwing precision!",
                "ability": "Can create and throw objects with deadly accuracy",
            },
            "female": {
                "name": "Female Titan",
                "emoji": "🩸",
                "color": discord.Color.magenta(),
                "height": "14m",
                "desc": "Agile and intelligent, with the ability to harden specific body parts!",
                "ability": "Selective hardening and Titan attraction",
            },
            "jaw": {
                "name": "Jaw Titan",
                "emoji": "🦷",
                "color": discord.Color.brown(),
                "height": "5m",
                "desc": "The smallest and fastest Titan with the strongest bite force!",
                "ability": "Can crush Titan armor and ODM gear with ease",
            },
            "cart": {
                "name": "Cart Titan",
                "emoji": "🐕",
                "color": discord.Color.brown(),
                "height": "4m",
                "desc": "A quadrupedal Titan built for endurance and long missions!",
                "ability": "Can maintain Titan form for months without tiring",
            },
            "warhammer": {
                "name": "War Hammer Titan",
                "emoji": "🔨",
                "color": discord.Color.purple(),
                "height": "15m",
                "desc": "Wields the power to create weapons from hardened Titan flesh!",
                "ability": "Can create any weapon from crystallized Titan flesh",
            },
        }
        
        data = titan_data[titan.value]
        
        embed = discord.Embed(
            title=f"{data['emoji']} {data['name']} Transformation",
            description=f"{data['desc']}",
            color=data["color"]
        )
        embed.add_field(name="Height", value=data["height"], inline=True)
        embed.add_field(name="Special Ability", value=data["ability"], inline=True)
        embed.add_field(name="⚡ Transformation Sequence",
                       value="Blood spurts → Titan flesh bursts forth → Steam rises → Titan roars! 💥",
                       inline=False)
        
        gif_url = await get_gif("transform", f"{titan.value} titan transformation")
        if gif_url:
            embed.set_image(url=gif_url)
        
        # Grant XP for transformation
        player = GameState.get_player(str(interaction.user.id), interaction.user.display_name)
        player.add_xp(25)
        GameState.save_player(player)
        
        embed.set_footer(text=f"+25 XP! | Level {player.level} now | You feel the power of the Titans coursing through you!")
        
        await interaction.response.send_message(embed=embed)

    # ── Gear Upgrade System ──────────────────────────────────────────────────

    @app_commands.command(name="gear_upgrade", description="Upgrade your ODM gear and equipment!")
    async def gear_upgrade(self, interaction: discord.Interaction):
        """View and upgrade your ODM gear components."""
        player = GameState.get_player(str(interaction.user.id), interaction.user.display_name)
        
        # Initialize gear data if not present
        if not hasattr(player, 'gear_data'):
            player.gear_data = {
                "blades": 1, "gas_tank": 1, "handles": 1, "thrusters": 1,
                "blade_xp": 0, "gas_xp": 0, "handle_xp": 0, "thruster_xp": 0,
            }
        
        gear = player.gear_data
        
        gear_names = {
            "blades": "⚔️ ODM Blades",
            "gas_tank": "⛽ Gas Tank",
            "handles": "🤲 Maneuver Handles",
            "thrusters": "💨 Thrusters",
        }
        
        upgrade_costs = {1: 100, 2: 250, 3: 500, 4: 1000, 5: 2000}
        
        embed = discord.Embed(
            title="🪂 ODM Gear Upgrades",
            description=f"**Scout:** {player.scout_name}\n**Rank:** {player.rank}\n",
            color=discord.Color.teal()
        )
        
        for gear_key, display_name in gear_names.items():
            level = gear.get(gear_key, 1)
            xp = gear.get(f"{gear_key}_xp", 0)
            next_cost = upgrade_costs.get(level, 2000)
            
            if level >= 5:
                status = "⭐ MAX LEVEL"
                bar = "[██████████]"
            else:
                needed = level * 100
                percent = min(100, int(xp / needed * 100))
                filled = percent // 10
                bar = f"[{'█' * filled}{'░' * (10-filled)}]"
                status = f"Cost: {next_cost} XP"
            
            embed.add_field(
                name=f"{display_name} (Level {level})",
                value=f"{bar} {xp}/{needed if level < 5 else 'MAX'} XP | {status}",
                inline=False
            )
        
        embed.add_field(
            name="📊 Gear Effects",
            value=(
                "• ⚔️ Blades: Attack damage +10% per level\n"
                "• ⛽ Gas Tank: Grapple distance +15% per level\n"
                "• 🤲 Handles: Maneuver speed +10% per level\n"
                "• 💨 Thrusters: Dash speed +20% per level"
            ),
            inline=False
        )
        
        # Calculate total gear bonus
        total_bonus = sum(gear.get(g, 1) - 1 for g in gear_names.keys()) * 5
        embed.add_field(name="🎯 Total Gear Bonus", value=f"+{total_bonus}% Combat Effectiveness", inline=False)
        
        embed.set_footer(text="⚠️ Use /fight and /odm_training to earn gear XP!")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="scout_ranking", description="View the top Scouts on the leaderboard!")
    async def scout_ranking(self, interaction: discord.Interaction):
        """View the top-ranked Scouts."""
        
        if not GameState._players:
            GameState._load()
        
        sorted_players = sorted(
            GameState._players.values(),
            key=lambda p: (p.level, p.xp, p.wins),
            reverse=True
        )[:10]
        
        embed = discord.Embed(
            title="🏆 Scout Leaderboard - Top 10",
            description="The finest soldiers humanity has to offer!",
            color=discord.Color.gold()
        )
        
        medals = ["🥇", "🥈", "🥉"]
        
        for i, p in enumerate(sorted_players):
            medal = medals[i] if i < 3 else f"  {i+1}."
            embed.add_field(
                name=f"{medal} **{p.scout_name}** (Level {p.level} - {p.rank})",
                value=(
                    f"👤 {p.username}\n"
                    f"⚔️ Wins: {p.wins} | 🗡️ Kills: {p.kills} | 🏃 XP: {p.xp}/{p.xp_needed}\n"
                    f"📊 Win Rate: {(p.wins/(p.wins+p.losses)*100) if (p.wins+p.losses) > 0 else 0:.1f}%"
                ),
                inline=False
            )
        
        embed.set_footer(text="Glory to the Scout Regiment!")
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Abilities(bot))
