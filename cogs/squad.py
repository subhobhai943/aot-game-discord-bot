"""Survey Corps Squad management system cog."""
from __future__ import annotations
import re
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from utils.db import Database
from utils.game_state import GameState


SQUAD_LEVELS = {
    1: {"cost": 0, "desc": "Standard Squad. Assemble your vanguard soldiers!"},
    2: {"cost": 1000, "desc": "🛡️ Tactical Scouts unlocked: **All members receive +10% XP** from PvE/PvP battles!"},
    3: {"cost": 2500, "desc": "💰 Regiment Finance unlocked: **All members receive +10% Coins** from PvE/PvP battles!"},
    4: {"cost": 5000, "desc": "⚔️ ODM Specialists unlocked: **All members receive +5% ATK damage** in battles!"},
    5: {"cost": 10000, "desc": "🩸 Survey Corps Vanguard unlocked: **All members receive +10% Max HP** in battles!"}
}


class Squad(commands.Cog):
    """⚔️ Survey Corps Squads — Create, join, and level up squads to unlock permanent team combat buffs."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _clean_name(self, name: str) -> Optional[str]:
        cleaned = name.strip()
        if not (3 <= len(cleaned) <= 15):
            return None
        # Allow alphanumeric, spaces, and dashes
        if not re.match(r"^[a-zA-Z0-9\s\-]+$", cleaned):
            return None
        return cleaned

    # ── Create Command ────────────────────────────────────────────────────────
    @commands.group(name="squad", invoke_without_command=True, help="Scout squad management commands. Use >squad info to see details.")
    async def squad_group(self, ctx: commands.Context):
        # Default to info if no subcommand is used
        await self.info_prefix(ctx)

    @squad_group.command(name="create", help="Create a new Squad. Costs 500 coins. Usage: >squad create <name>")
    async def create_prefix(self, ctx: commands.Context, *, name: str):
        player = await GameState.get_player(str(ctx.author.id), ctx.author.display_name)
        if player.squad:
            await ctx.send(f"❌ You are already in squad **{player.squad}**! Leave it first using `>squad leave`.")
            return

        cleaned_name = self._clean_name(name)
        if not cleaned_name:
            await ctx.send("❌ Invalid squad name! Names must be 3-15 characters and contain only letters, numbers, spaces, or dashes.")
            return

        if player.coins < 500:
            await ctx.send(f"❌ You don't have enough coins! Creating a squad costs `500 coins` but you only have `{player.coins}`.")
            return

        # Check if name is taken
        existing = await Database.get_squad(cleaned_name)
        if existing:
            await ctx.send(f"❌ A squad named **{cleaned_name}** already exists! Choose another name.")
            return

        # Deduct coins and create
        player.coins -= 500
        player.squad = cleaned_name
        player.squad_level = 1
        
        squad_data = {
            "name": cleaned_name,
            "creator_id": str(ctx.author.id),
            "level": 1,
            "coins_donated": 0
        }
        
        await Database.save_squad(squad_data)
        await GameState.save_player(player)

        embed = discord.Embed(
            title="⚔️ Vanguard Squad Created!",
            description=(
                f"**{ctx.author.mention}** spent **500 coins** and established the squad **{cleaned_name}**!\n\n"
                f"📢 Share the name with other scouts and use `>squad join {cleaned_name}` to assemble your vanguard regiment!"
            ),
            color=discord.Color.green()
        )
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Attack_on_Titan_logo.png/640px-Attack_on_Titan_logo.png")
        await ctx.send(embed=embed)

    @app_commands.command(name="squad-create", description="Establish a new Survey Corps Vanguard Squad (Costs 500 coins)")
    @app_commands.describe(name="Name of the squad (3-15 chars, alphanumeric/spaces)")
    async def create_slash(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        player = await GameState.get_player(str(interaction.user.id), interaction.user.display_name)
        if player.squad:
            await interaction.followup.send(f"❌ You are already in squad **{player.squad}**! Leave it first.", ephemeral=True)
            return

        cleaned_name = self._clean_name(name)
        if not cleaned_name:
            await interaction.followup.send("❌ Invalid squad name! Must be 3-15 chars and contain alphanumeric/spaces only.", ephemeral=True)
            return

        if player.coins < 500:
            await interaction.followup.send(f"❌ You don't have enough coins! You need `500 coins` but only have `{player.coins}`.", ephemeral=True)
            return

        existing = await Database.get_squad(cleaned_name)
        if existing:
            await interaction.followup.send(f"❌ A squad named **{cleaned_name}** already exists!", ephemeral=True)
            return

        player.coins -= 500
        player.squad = cleaned_name
        player.squad_level = 1
        
        squad_data = {
            "name": cleaned_name,
            "creator_id": str(interaction.user.id),
            "level": 1,
            "coins_donated": 0
        }
        
        await Database.save_squad(squad_data)
        await GameState.save_player(player)

        embed = discord.Embed(
            title="⚔️ Vanguard Squad Created!",
            description=(
                f"**{interaction.user.mention}** spent **500 coins** and established the squad **{cleaned_name}**!\n\n"
                f"📢 Tell your friends to run `/squad-join {cleaned_name}` to join!"
            ),
            color=discord.Color.green()
        )
        embed.set_thumbnail(url="https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Attack_on_Titan_logo.png/640px-Attack_on_Titan_logo.png")
        await interaction.followup.send(embed=embed)

    # ── Join Command ──────────────────────────────────────────────────────────
    @squad_group.command(name="join", help="Join an existing squad. Usage: >squad join <name>")
    async def join_prefix(self, ctx: commands.Context, *, name: str):
        player = await GameState.get_player(str(ctx.author.id), ctx.author.display_name)
        if player.squad:
            await ctx.send(f"❌ You are already in squad **{player.squad}**! Leave it first using `>squad leave`.")
            return

        squad = await Database.get_squad(name)
        if not squad:
            await ctx.send(f"❌ No squad found named **{name}**.")
            return

        members = await Database.get_squad_members(squad["name"])
        if len(members) >= 10:
            await ctx.send(f"❌ Squad **{squad['name']}** is currently full (max 10 members)!")
            return

        # Join squad
        player.squad = squad["name"]
        player.squad_level = squad["level"]
        await GameState.save_player(player)

        await ctx.send(f"✅ **{ctx.author.mention}** joined squad **{squad['name']}**! Welcome to the vanguard!")

    @app_commands.command(name="squad-join", description="Join an existing Survey Corps Vanguard Squad")
    @app_commands.describe(name="Name of the squad to join")
    async def join_slash(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        player = await GameState.get_player(str(interaction.user.id), interaction.user.display_name)
        if player.squad:
            await interaction.followup.send(f"❌ You are already in squad **{player.squad}**! Leave it first.", ephemeral=True)
            return

        squad = await Database.get_squad(name)
        if not squad:
            await interaction.followup.send(f"❌ No squad found named **{name}**.", ephemeral=True)
            return

        members = await Database.get_squad_members(squad["name"])
        if len(members) >= 10:
            await interaction.followup.send(f"❌ Squad **{squad['name']}** is full (max 10 members)!", ephemeral=True)
            return

        player.squad = squad["name"]
        player.squad_level = squad["level"]
        await GameState.save_player(player)

        await interaction.followup.send(f"✅ **{interaction.user.mention}** joined squad **{squad['name']}**! Welcome to the vanguard!")

    # ── Info Command ──────────────────────────────────────────────────────────
    @squad_group.command(name="info", help="View squad stats and member list. Usage: >squad info [name]")
    async def info_prefix(self, ctx: commands.Context, *, name: Optional[str] = None):
        target_squad = name
        if not target_squad:
            player = await GameState.get_player(str(ctx.author.id), ctx.author.display_name)
            target_squad = player.squad
            if not target_squad:
                await ctx.send("❌ You are not in any squad! Use `>squad create <name>` or `>squad join <name>` to get started.")
                return

        squad = await Database.get_squad(target_squad)
        if not squad:
            await ctx.send(f"❌ No squad found named **{target_squad}**.")
            return

        embed = await self._build_info_embed(squad)
        await ctx.send(embed=embed)

    @app_commands.command(name="squad-info", description="View squad stats and member list")
    @app_commands.describe(name="Squad name (leave blank to view your own)")
    async def info_slash(self, interaction: discord.Interaction, name: Optional[str] = None):
        await interaction.response.defer()
        target_squad = name
        if not target_squad:
            player = await GameState.get_player(str(interaction.user.id), interaction.user.display_name)
            target_squad = player.squad
            if not target_squad:
                await interaction.followup.send("❌ You are not in any squad! Create or join one first.", ephemeral=True)
                return

        squad = await Database.get_squad(target_squad)
        if not squad:
            await interaction.followup.send(f"❌ No squad found named **{target_squad}**.", ephemeral=True)
            return

        embed = await self._build_info_embed(squad)
        await interaction.followup.send(embed=embed)

    async def _build_info_embed(self, squad: dict) -> discord.Embed:
        members = await Database.get_squad_members(squad["name"])
        
        creator_user = self.bot.get_user(int(squad["creator_id"]))
        creator_name = creator_user.display_name if creator_user else f"ID: {squad['creator_id']}"

        embed = discord.Embed(
            title=f"🛡️ Vanguard Squad: {squad['name']}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Commander / Founder", value=creator_name, inline=True)
        embed.add_field(name="Squad Level", value=f"Level **{squad['level']}/5**", inline=True)
        
        # Next level progress
        donated = squad["coins_donated"]
        curr_lvl = squad["level"]
        if curr_lvl >= 5:
            bar = "[██████████] MAX"
        else:
            needed = SQUAD_LEVELS[curr_lvl + 1]["cost"]
            percent = min(100, int(donated / needed * 100))
            filled = percent // 10
            bar = f"[{'█' * filled}{'░' * (10-filled)}] {percent}% (`{donated}/{needed} coins`)"
            
        embed.add_field(name="📈 Level Progress", value=bar, inline=False)

        # Active unlocks
        unlocks = []
        for lv in range(2, curr_lvl + 1):
            unlocks.append(SQUAD_LEVELS[lv]["desc"])
        unlocks_str = "\n".join(unlocks) if unlocks else "None yet (level up squad to unlock buffs)"
        embed.add_field(name="🔮 Active Regiment Buffs:", value=unlocks_str, inline=False)

        # Next unlock preview
        if curr_lvl < 5:
            next_unlock = SQUAD_LEVELS[curr_lvl + 1]["desc"]
            embed.add_field(name="✨ Next Level Unlock:", value=next_unlock, inline=False)

        # Member list
        member_lines = []
        for idx, m in enumerate(members):
            creator_marker = " 👑" if m["user_id"] == squad["creator_id"] else ""
            member_lines.append(f"`{idx + 1}.` **{m['username']}** (Level {m['level']}){creator_marker} | ⚔️ {m['wins']} wins")
            
        embed.add_field(name=f"👥 Vanguard Soldiers ({len(members)}/10):", value="\n".join(member_lines), inline=False)
        embed.set_footer(text="Help humanity reclaim the walls by working together!")
        return embed

    # ── Donate Command ────────────────────────────────────────────────────────
    @squad_group.command(name="donate", help="Donate coins to level up your squad. Usage: >squad donate <amount>")
    async def donate_prefix(self, ctx: commands.Context, amount: int):
        player = await GameState.get_player(str(ctx.author.id), ctx.author.display_name)
        if not player.squad:
            await ctx.send("❌ You are not in any squad! Create or join one first.")
            return

        if amount <= 0:
            await ctx.send("❌ Amount must be a positive integer!")
            return

        if player.coins < amount:
            await ctx.send(f"❌ You don't have enough coins! You have `{player.coins} coins` but tried to donate `{amount}`.")
            return

        squad = await Database.get_squad(player.squad)
        if not squad:
            await ctx.send("❌ Could not retrieve your squad details from database.")
            return

        if squad["level"] >= 5:
            await ctx.send("❌ Your squad is already at the maximum level (5)!")
            return

        # Apply donation
        player.coins -= amount
        squad["coins_donated"] += amount

        # Check level up loop
        leveled = False
        while squad["level"] < 5:
            next_lvl = squad["level"] + 1
            needed = SQUAD_LEVELS[next_lvl]["cost"]
            if squad["coins_donated"] >= needed:
                squad["level"] = next_lvl
                leveled = True
            else:
                break

        await Database.save_squad(squad)
        # Update transient squad level on cached player object
        player.squad_level = squad["level"]
        await GameState.save_player(player)

        await ctx.send(
            f"💰 **{ctx.author.mention}** donated **{amount} coins** to squad **{squad['name']}**!\n"
            f"Current total donated: `{squad['coins_donated']} coins`."
        )
        if leveled:
            await ctx.send(
                f"🎉 **SQUAD LEVEL UP!** **{squad['name']}** has reached **Level {squad['level']}**!\n"
                f"{SQUAD_LEVELS[squad['level']]['desc']}"
            )
            # Sync transient squad level for all members in the current runtime cache
            for p in GameState._players.values():
                if p.squad == squad["name"]:
                    p.squad_level = squad["level"]

    @app_commands.command(name="squad-donate", description="Donate coins to level up your Survey Corps Squad")
    @app_commands.describe(amount="Amount of coins to donate")
    async def donate_slash(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer()
        player = await GameState.get_player(str(interaction.user.id), interaction.user.display_name)
        if not player.squad:
            await interaction.followup.send("❌ You are not in any squad! Create or join one first.", ephemeral=True)
            return

        if amount <= 0:
            await interaction.followup.send("❌ Amount must be a positive integer!", ephemeral=True)
            return

        if player.coins < amount:
            await interaction.followup.send(f"❌ You don't have enough coins! You only have `{player.coins}`.", ephemeral=True)
            return

        squad = await Database.get_squad(player.squad)
        if not squad:
            await interaction.followup.send("❌ Could not retrieve squad details.", ephemeral=True)
            return

        if squad["level"] >= 5:
            await interaction.followup.send("❌ Your squad is already at max level (5)!", ephemeral=True)
            return

        player.coins -= amount
        squad["coins_donated"] += amount

        leveled = False
        while squad["level"] < 5:
            next_lvl = squad["level"] + 1
            needed = SQUAD_LEVELS[next_lvl]["cost"]
            if squad["coins_donated"] >= needed:
                squad["level"] = next_lvl
                leveled = True
            else:
                break

        await Database.save_squad(squad)
        player.squad_level = squad["level"]
        await GameState.save_player(player)

        msg = f"💰 **{interaction.user.mention}** donated **{amount} coins** to squad **{squad['name']}**!\n"
        if leveled:
            msg += f"🎉 **SQUAD LEVEL UP!** **{squad['name']}** has reached **Level {squad['level']}**!\n"
            msg += f"{SQUAD_LEVELS[squad['level']]['desc']}"
            # Sync transient squad level
            for p in GameState._players.values():
                if p.squad == squad["name"]:
                    p.squad_level = squad["level"]
        await interaction.followup.send(msg)

    # ── Leave Command ─────────────────────────────────────────────────────────
    @squad_group.command(name="leave", help="Leave your current squad. WARNING: Disbands if you are the Commander!")
    async def leave_prefix(self, ctx: commands.Context):
        player = await GameState.get_player(str(ctx.author.id), ctx.author.display_name)
        if not player.squad:
            await ctx.send("❌ You are not in any squad!")
            return

        squad = await Database.get_squad(player.squad)
        if not squad:
            player.squad = None
            player.squad_level = 0
            await GameState.save_player(player)
            await ctx.send("✅ Left squad.")
            return

        is_creator = squad["creator_id"] == str(ctx.author.id)

        if is_creator:
            # Delete/Disband squad
            sname = squad["name"]
            await Database.delete_squad(sname)
            # Sync all cached users in this squad
            for p in list(GameState._players.values()):
                if p.squad == sname:
                    p.squad = None
                    p.squad_level = 0
            await ctx.send(f"⚠️ **Commander {ctx.author.mention}** left and successfully **disbanded** the squad **{sname}**.")
        else:
            sname = player.squad
            player.squad = None
            player.squad_level = 0
            await GameState.save_player(player)
            await ctx.send(f"✅ **{ctx.author.mention}** left the squad **{sname}**.")

    @app_commands.command(name="squad-leave", description="Leave your current Survey Corps Squad (WARNING: Disbands if Commander)")
    async def leave_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        player = await GameState.get_player(str(interaction.user.id), interaction.user.display_name)
        if not player.squad:
            await interaction.followup.send("❌ You are not in any squad!", ephemeral=True)
            return

        squad = await Database.get_squad(player.squad)
        if not squad:
            player.squad = None
            player.squad_level = 0
            await GameState.save_player(player)
            await interaction.followup.send("✅ Left squad.", ephemeral=True)
            return

        is_creator = squad["creator_id"] == str(interaction.user.id)

        if is_creator:
            sname = squad["name"]
            await Database.delete_squad(sname)
            for p in list(GameState._players.values()):
                if p.squad == sname:
                    p.squad = None
                    p.squad_level = 0
            await interaction.followup.send(f"⚠️ **Commander {interaction.user.mention}** left and successfully **disbanded** the squad **{sname}**.")
        else:
            sname = player.squad
            player.squad = None
            player.squad_level = 0
            await GameState.save_player(player)
            await interaction.followup.send(f"✅ **{interaction.user.mention}** left the squad **{sname}**.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Squad(bot))
