"""PvE battle cog.
Uses the external aot-toolkit library (AoTDatabase / CombatSimulator) when available,
falls back gracefully to the internal utils.game_state engine if the library is missing.
"""
from __future__ import annotations
import random
import discord
from discord.ext import commands
from discord import app_commands
from utils.game_state import (
    GameState, TITAN_STATS, get_titan_image,
    calc_move, titan_ai_move, CHARACTERS,
)

# ── Try to load the external aot-toolkit library ──────────────────────────
try:
    from aot.core.database import AoTDatabase
    from aot.engine.combat import CombatSimulator
    _db        = AoTDatabase()
    _simulator = CombatSimulator(_db)
    _HAS_LIB   = True
except ImportError:
    _HAS_LIB   = False
    _db        = None
    _simulator = None


def _hp_bar(current: int, maximum: int, length: int = 10) -> str:
    filled = max(0, int((current / maximum) * length))
    bar    = "\u2588" * filled + "\u2591" * (length - filled)
    pct    = int((current / maximum) * 100)
    return f"`[{bar}]` {current}/{maximum} ({pct}%)"


def _battle_embed(session) -> discord.Embed:
    t_stats = TITAN_STATS.get(session.titan_name, {})
    rarity  = t_stats.get("rarity", "Common")
    embed   = discord.Embed(
        title=f"\u2694\ufe0f {session.scout_name} vs {session.titan_name} \u2014 Round {session.round_num}",
        color=RARITY_COLOR.get(rarity, 0x5599FF)
    )
    embed.add_field(
        name=f"\U0001f7e2 {session.scout_name} (Scout)",
        value=_hp_bar(session.scout_hp, session.scout_max_hp),
        inline=False
    )
    embed.add_field(
        name=f"\U0001f534 {session.titan_name} ({RARITY_EMOJI.get(rarity, '')} {rarity})",
        value=_hp_bar(session.titan_hp, session.titan_max_hp),
        inline=False
    )
    embed.set_thumbnail(url=get_titan_image(session.titan_name))
    return embed


class Battle(commands.Cog):
    """PvE battle system."""

    def __init__(self, bot):
        self.bot = bot

    # ── /simulate  (uses external library if available) ───────────────────
    @app_commands.command(name="simulate", description="Cinematic narrative battle (uses aot-toolkit library)")
    @app_commands.describe(character="Scout name", titan="Titan to fight")
    async def simulate(self, interaction: discord.Interaction, character: str, titan: str):
        await interaction.response.defer()
        if not _HAS_LIB:
            await interaction.followup.send(
                "\u274c The `aot-toolkit` library is not installed.\n"
                "Install it with `pip install aot-toolkit`, or use `Aot fight <character> vs <titan>` instead."
            )
            return
        try:
            report = _simulator.simulate_encounter(character, titan)
        except Exception as e:
            await interaction.followup.send(f"\u274c Simulation failed: `{e}`")
            return
        embed = discord.Embed(
            title=f"\u2694\ufe0f {character} vs {titan}",
            description=f"```\n{str(report)[:1990]}\n```",
            color=discord.Color.red()
        )
        embed.set_footer(text="\U0001fa7a Wings of Freedom | AOT-Toolkit")
        await interaction.followup.send(embed=embed)

    # ── /attack (slash) ───────────────────────────────────────────────────
    @app_commands.command(name="attack", description="Attack during a PvE battle")
    @app_commands.choices(move=[
        app_commands.Choice(name="\u2694\ufe0f Slash",          value="slash"),
        app_commands.Choice(name="\U0001fa7a ODM Dash",          value="odm_dash"),
        app_commands.Choice(name="\U0001f4a5 Thunder Spear",     value="thunder_spear"),
        app_commands.Choice(name="\U0001f300 Spiral Cut",        value="spiral_cut"),
        app_commands.Choice(name="\U0001f9f1 Titan Smash",       value="titan_smash"),
        app_commands.Choice(name="\U0001f6e1\ufe0f Defend",      value="defend"),
    ])
    async def attack_slash(self, interaction: discord.Interaction, move: str):
        await interaction.response.defer()
        session = GameState.get_battle(str(interaction.user.id))
        if not session or not session.active:
            await interaction.followup.send("\u274c No active battle! Use `Aot fight <character> vs <titan>`.")
            return
        await self._process_move(interaction.followup.send, str(interaction.user.id),
                                 interaction.user.display_name, move, session)

    # ── Aot fight <character> vs <titan>  (prefix PvE) ────────────────────
    @commands.command(name="fight", aliases=["pve", "startbattle"])
    async def fight(self, ctx: commands.Context, *, args: str = ""):
        """Start a PvE battle.\nUsage: Aot fight <character> vs <titan>
        Example: Aot fight Levi Ackerman vs Pure Titan"""
        if " vs " not in args:
            await ctx.send(
                "\u274c Usage: `Aot fight <character> vs <titan>`\n"
                f"Characters: `{'`, `'.join(CHARACTERS)}`\n"
                f"Titans: `{'`, `'.join(TITAN_STATS.keys())}`"
            )
            return
        parts     = args.split(" vs ", 1)
        character = parts[0].strip().title()
        titan     = parts[1].strip().title()
        c_match   = next((c for c in CHARACTERS if c.lower() == character.lower()), None)
        t_match   = next((t for t in TITAN_STATS if t.lower() == titan.lower()), None)
        if not c_match:
            await ctx.send(f"\u274c Unknown character. Options: `{'`, `'.join(CHARACTERS)}`")
            return
        if not t_match:
            await ctx.send(f"\u274c Unknown titan. Options: `{'`, `'.join(TITAN_STATS.keys())}`")
            return
        if GameState.get_battle(str(ctx.author.id)):
            await ctx.send("\u274c You already have an active battle! Finish it or use `Aot flee`.")
            return
        session = GameState.start_battle(str(ctx.author.id), c_match, t_match, ctx.channel.id)
        embed   = _battle_embed(session)
        embed.set_footer(text="Use: Aot slash | Aot odmdash | Aot spear | Aot spiral | Aot smash | Aot defend")
        await ctx.send(embed=embed)

    # ── Prefix move commands  (NO aliases that clash with gifs.py) ─────────
    # NOTE: gifs.py owns: odm, thunder_spear, spear, slice, charge, etc.
    # We use distinct names: odmslash, tspear, spiralcut, smash, pvedefend
    async def _do_move(self, ctx: commands.Context, move: str):
        session = GameState.get_battle(str(ctx.author.id))
        if not session or not session.active:
            await ctx.send("\u274c No active PvE battle. Start one with `Aot fight <character> vs <titan>`.")
            return
        await self._process_move(ctx.send, str(ctx.author.id), ctx.author.display_name, move, session)

    @commands.command(name="slash", aliases=["swordfight"])
    async def slash(self, ctx): await self._do_move(ctx, "slash")

    @commands.command(name="odmdash", aliases=["odmswing"])
    async def odmdash(self, ctx): await self._do_move(ctx, "odm_dash")

    @commands.command(name="tspear", aliases=["thunderspear"])
    async def tspear(self, ctx): await self._do_move(ctx, "thunder_spear")

    @commands.command(name="spiralcut", aliases=["spiral"])
    async def spiralcut(self, ctx): await self._do_move(ctx, "spiral_cut")

    @commands.command(name="smash", aliases=["titansmash"])
    async def smash(self, ctx): await self._do_move(ctx, "titan_smash")

    @commands.command(name="pvedefend", aliases=["block"])
    async def pvedefend(self, ctx): await self._do_move(ctx, "defend")

    @commands.command(name="flee", aliases=["run", "escapebattle"])
    async def flee(self, ctx: commands.Context):
        """Flee from your current PvE battle. Usage: Aot flee"""
        session = GameState.get_battle(str(ctx.author.id))
        if not session or not session.active:
            await ctx.send("\u274c No active battle to flee from.")
            return
        GameState.end_battle(str(ctx.author.id))
        await ctx.send(f"\U0001f3c3 **{ctx.author.display_name}** fled from the **{session.titan_name}**!")

    # ── Shared move processor ─────────────────────────────────────────────
    async def _process_move(self, send_fn, user_id: str, username: str, move: str, session):
        log = []
        dmg, missed, desc = calc_move(move, attacker_is_scout=True)
        if move == "defend":
            log.append(f"\U0001f6e1\ufe0f **{session.scout_name}** defends!")
        elif missed:
            log.append(f"\u274c **{session.scout_name}** {desc} \u2014 MISSED!")
        else:
            session.titan_hp = max(0, session.titan_hp - dmg)
            log.append(f"\u2705 **{session.scout_name}** {desc} \u2014 **{dmg} DMG**!")

        if session.titan_hp <= 0:
            session.active = False
            player  = GameState.get_player(user_id, username)
            xp_gain = TITAN_STATS.get(session.titan_name, {}).get("hp", 200) // 4
            player.add_xp(xp_gain); player.coins += 25; player.kills += 1
            GameState.save_player(player)
            GameState.end_battle(user_id)
            embed = discord.Embed(
                title="\U0001f3c6 Victory!",
                description=f"**{session.scout_name}** slew the **{session.titan_name}**!\n" + "\n".join(log),
                color=0x55AA55
            )
            embed.add_field(name="\u26a1 XP", value=f"+{xp_gain}", inline=True)
            embed.add_field(name="\U0001f4b0 Coins", value="+25", inline=True)
            await send_fn(embed=embed)
            return

        t_dmg, t_missed, t_desc = titan_ai_move()
        if move == "defend": t_dmg = t_dmg // 2
        if t_missed:
            log.append(f"\U0001f4a8 The **{session.titan_name}** {t_desc} \u2014 MISS!")
        else:
            session.scout_hp = max(0, session.scout_hp - t_dmg)
            log.append(f"\U0001f4a5 The **{session.titan_name}** {t_desc} \u2014 **{t_dmg} DMG**!")
        session.round_num += 1

        if session.scout_hp <= 0:
            session.active = False
            player = GameState.get_player(user_id, username)
            player.losses += 1; player.add_xp(15)
            GameState.save_player(player)
            GameState.end_battle(user_id)
            embed = discord.Embed(
                title="\U0001f480 Defeated!",
                description=f"**{session.scout_name}** was defeated!\n" + "\n".join(log),
                color=0xFF3333
            )
            await send_fn(embed=embed)
            return

        embed = _battle_embed(session)
        embed.add_field(name="\U0001f4dc This Round", value="\n".join(log), inline=False)
        embed.set_footer(text="Aot slash | Aot odmdash | Aot tspear | Aot spiralcut | Aot smash | Aot pvedefend")
        await send_fn(embed=embed)


async def setup(bot):
    await bot.add_cog(Battle(bot))
