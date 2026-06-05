"""Cinematic PvE battle simulation cog (prefix-based fallback)."""
import discord
from discord.ext import commands
from discord import app_commands
import random
from utils.game_state import (
    GameState, TITAN_STATS, TITAN_IMAGES, MOVES,
    RARITY_COLOR, RARITY_EMOJI, SURVEY_CORPS_ICON,
    calc_move, titan_ai_move, CHARACTERS, TITANS
)


def _hp_bar(current: int, maximum: int, length: int = 10) -> str:
    filled = max(0, int((current / maximum) * length))
    bar = "█" * filled + "░" * (length - filled)
    pct = int((current / maximum) * 100)
    return f"`[{bar}]` {current}/{maximum} ({pct}%)"


class Battle(commands.Cog):
    """PvE battle system — fight titans as an AoT character!"""

    def __init__(self, bot):
        self.bot = bot

    # ── Slash: /simulate ──────────────────────────────────────────────────
    @app_commands.command(name="simulate", description="Cinematic narrative battle simulation")
    @app_commands.describe(character="Scout name (e.g. Levi Ackerman)", titan="Titan to fight")
    async def simulate(self, interaction: discord.Interaction, character: str, titan: str):
        await interaction.response.defer()
        c_match = next((c for c in CHARACTERS if c.lower() == character.lower()), None)
        t_match = next((t for t in TITAN_STATS if t.lower() == titan.lower()), None)
        if not c_match:
            await interaction.followup.send(f"❌ Unknown character. Options: {', '.join(CHARACTERS)}")
            return
        if not t_match:
            await interaction.followup.send(f"❌ Unknown titan. Options: {', '.join(TITAN_STATS.keys())}")
            return
        session = GameState.start_battle(str(interaction.user.id), c_match, t_match, interaction.channel_id)
        embed = _battle_state_embed(session)
        embed.set_footer(text="Use /attack <move> to fight! Moves: slash, odm_dash, thunder_spear, spiral_cut, titan_smash, defend")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="attack", description="Attack during a PvE battle")
    @app_commands.describe(move="Your move: slash, odm_dash, thunder_spear, spiral_cut, titan_smash, defend")
    @app_commands.choices(move=[
        app_commands.Choice(name="⚔️ Slash",          value="slash"),
        app_commands.Choice(name="🪺 ODM Dash",        value="odm_dash"),
        app_commands.Choice(name="💥 Thunder Spear",   value="thunder_spear"),
        app_commands.Choice(name="🌀 Spiral Cut",      value="spiral_cut"),
        app_commands.Choice(name="🧱 Titan Smash",     value="titan_smash"),
        app_commands.Choice(name="🛡️ Defend",          value="defend"),
    ])
    async def attack(self, interaction: discord.Interaction, move: str):
        await interaction.response.defer(ephemeral=False)
        session = GameState.get_battle(str(interaction.user.id))
        if not session or not session.active:
            await interaction.followup.send("❌ No active battle! Start one with `/simulate`.")
            return
        log = []
        # Player move
        dmg, missed, desc = calc_move(move, attacker_is_scout=True)
        if move == "defend":
            log.append(f"🛡️ **{session.scout_name}** takes a defensive stance!")
        elif missed:
            log.append(f"❌ **{session.scout_name}** {desc} — MISSED!")
        else:
            session.titan_hp = max(0, session.titan_hp - dmg)
            log.append(f"✅ **{session.scout_name}** {desc} — **{dmg} DMG** to the titan!")

        if session.titan_hp <= 0:
            session.active = False
            player = GameState.get_player(str(interaction.user.id), interaction.user.display_name)
            xp_gain = TITAN_STATS.get(session.titan_name, {}).get("hp", 200) // 4
            player.add_xp(xp_gain)
            player.coins += 25
            player.kills += 1
            GameState.save_player(player)
            GameState.end_battle(str(interaction.user.id))
            embed = discord.Embed(
                title="🏆 Victory!",
                description=f"**{session.scout_name}** slew the **{session.titan_name}**!\n" + "\n".join(log),
                color=0x55AA55
            )
            embed.add_field(name="⚡ XP Earned", value=f"+{xp_gain}", inline=True)
            embed.add_field(name="💰 Coins",     value="+25",          inline=True)
            embed.set_thumbnail(url=SURVEY_CORPS_ICON)
            await interaction.followup.send(embed=embed)
            return

        # Titan counter-attack
        t_dmg, t_missed, t_desc = titan_ai_move()
        defending = (move == "defend")
        if defending:
            t_dmg = t_dmg // 2
        if t_missed:
            log.append(f"💨 The **{session.titan_name}** {t_desc} — MISS!")
        else:
            session.scout_hp = max(0, session.scout_hp - t_dmg)
            log.append(f"💥 The **{session.titan_name}** {t_desc} — **{t_dmg} DMG** to {session.scout_name}!")
            if defending:
                log[-1] += " *(halved by defend)*"

        session.round_num += 1

        if session.scout_hp <= 0:
            session.active = False
            player = GameState.get_player(str(interaction.user.id), interaction.user.display_name)
            player.losses += 1
            player.add_xp(15)
            GameState.save_player(player)
            GameState.end_battle(str(interaction.user.id))
            embed = discord.Embed(
                title="💀 Defeated!",
                description=f"**{session.scout_name}** was defeated by the **{session.titan_name}**!\n" + "\n".join(log),
                color=0xFF3333
            )
            embed.set_thumbnail(url=TITAN_IMAGES.get(session.titan_name, SURVEY_CORPS_ICON))
            await interaction.followup.send(embed=embed)
            return

        embed = _battle_state_embed(session)
        embed.add_field(name="📜 This Round", value="\n".join(log), inline=False)
        embed.set_footer(text="Use /attack <move> to continue! | Moves: slash, odm_dash, thunder_spear, spiral_cut, titan_smash, defend")
        await interaction.followup.send(embed=embed)

    # ── Prefix: >fight <character> <titan> ───────────────────────────────
    @commands.command(name="fight", aliases=["startbattle", "pve"])
    async def fight(self, ctx: commands.Context, *, args: str = ""):
        """Start a PvE battle. Usage: >fight <character> vs <titan>
        Example: >fight Levi Ackerman vs Pure Titan"""
        if " vs " not in args:
            await ctx.send(
                "❌ Usage: `>fight <character> vs <titan>`\n"
                f"Characters: `{'`, `'.join(CHARACTERS)}`\n"
                f"Titans: `{'`, `'.join(TITAN_STATS.keys())}`"
            )
            return
        parts = args.split(" vs ", 1)
        character = parts[0].strip().title()
        titan     = parts[1].strip().title()
        c_match = next((c for c in CHARACTERS if c.lower() == character.lower()), None)
        t_match = next((t for t in TITAN_STATS if t.lower() == titan.lower()), None)
        if not c_match:
            await ctx.send(f"❌ Unknown character. Options: `{'`, `'.join(CHARACTERS)}`")
            return
        if not t_match:
            await ctx.send(f"❌ Unknown titan. Options: `{'`, `'.join(TITAN_STATS.keys())}`")
            return
        if GameState.get_battle(str(ctx.author.id)):
            await ctx.send("❌ You already have an active battle! Finish it first.")
            return
        session = GameState.start_battle(str(ctx.author.id), c_match, t_match, ctx.channel.id)
        embed = _battle_state_embed(session)
        embed.set_footer(text="React or type: >slash | >odm | >spear | >spiral | >smash | >defend")
        await ctx.send(embed=embed)

    # ── Prefix move shortcuts ─────────────────────────────────────────────
    async def _do_move(self, ctx: commands.Context, move: str):
        session = GameState.get_battle(str(ctx.author.id))
        if not session or not session.active:
            await ctx.send("❌ No active battle! Start one with `>fight <character> vs <titan>`.")
            return
        log = []
        dmg, missed, desc = calc_move(move, attacker_is_scout=True)
        if move == "defend":
            log.append(f"🛡️ **{session.scout_name}** defends!")
        elif missed:
            log.append(f"❌ **{session.scout_name}** {desc} — MISSED!")
        else:
            session.titan_hp = max(0, session.titan_hp - dmg)
            log.append(f"✅ **{session.scout_name}** {desc} — **{dmg} DMG**!")

        if session.titan_hp <= 0:
            session.active = False
            player = GameState.get_player(str(ctx.author.id), ctx.author.display_name)
            xp_gain = TITAN_STATS.get(session.titan_name, {}).get("hp", 200) // 4
            player.add_xp(xp_gain); player.coins += 25; player.kills += 1
            GameState.save_player(player)
            GameState.end_battle(str(ctx.author.id))
            embed = discord.Embed(
                title="🏆 Victory!",
                description=f"**{session.scout_name}** slew the **{session.titan_name}**!\n" + "\n".join(log),
                color=0x55AA55
            )
            embed.add_field(name="⚡ XP", value=f"+{xp_gain}", inline=True)
            embed.add_field(name="💰 Coins", value="+25", inline=True)
            await ctx.send(embed=embed)
            return

        t_dmg, t_missed, t_desc = titan_ai_move()
        if move == "defend": t_dmg = t_dmg // 2
        if t_missed:
            log.append(f"💨 The **{session.titan_name}** {t_desc} — MISS!")
        else:
            session.scout_hp = max(0, session.scout_hp - t_dmg)
            log.append(f"💥 The **{session.titan_name}** {t_desc} — **{t_dmg} DMG**!")

        session.round_num += 1

        if session.scout_hp <= 0:
            session.active = False
            player = GameState.get_player(str(ctx.author.id), ctx.author.display_name)
            player.losses += 1; player.add_xp(15)
            GameState.save_player(player)
            GameState.end_battle(str(ctx.author.id))
            embed = discord.Embed(
                title="💀 Defeated!",
                description=f"**{session.scout_name}** was defeated!\n" + "\n".join(log),
                color=0xFF3333
            )
            await ctx.send(embed=embed)
            return

        embed = _battle_state_embed(session)
        embed.add_field(name="📜 This Round", value="\n".join(log), inline=False)
        embed.set_footer(text=">slash | >odm | >spear | >spiral | >smash | >defend")
        await ctx.send(embed=embed)

    @commands.command(name="slash")
    async def slash(self, ctx): await self._do_move(ctx, "slash")

    @commands.command(name="odm", aliases=["odmdash"])
    async def odm(self, ctx): await self._do_move(ctx, "odm_dash")

    @commands.command(name="spear", aliases=["thunderspear"])
    async def spear(self, ctx): await self._do_move(ctx, "thunder_spear")

    @commands.command(name="spiral", aliases=["spiralcut"])
    async def spiral(self, ctx): await self._do_move(ctx, "spiral_cut")

    @commands.command(name="smash", aliases=["titansmash"])
    async def smash(self, ctx): await self._do_move(ctx, "titan_smash")

    @commands.command(name="defend", aliases=["block"])
    async def defend(self, ctx): await self._do_move(ctx, "defend")

    @commands.command(name="flee", aliases=["run", "escapebattle"])
    async def flee(self, ctx: commands.Context):
        """Flee from your current PvE battle."""
        session = GameState.get_battle(str(ctx.author.id))
        if not session or not session.active:
            await ctx.send("❌ No active battle to flee from.")
            return
        GameState.end_battle(str(ctx.author.id))
        await ctx.send(f"🏃 **{ctx.author.display_name}** fled from the **{session.titan_name}**! Battle ended.")


def _battle_state_embed(session) -> discord.Embed:
    t_stats = TITAN_STATS.get(session.titan_name, {})
    rarity  = t_stats.get("rarity", "Common")
    color   = RARITY_COLOR.get(rarity, 0x5599FF)
    embed   = discord.Embed(
        title=f"⚔️ {session.scout_name} vs {session.titan_name} — Round {session.round_num}",
        color=color
    )
    embed.add_field(
        name=f"🟢 {session.scout_name} (Scout)",
        value=_hp_bar(session.scout_hp, session.scout_max_hp),
        inline=False
    )
    embed.add_field(
        name=f"🔴 {session.titan_name} ({RARITY_EMOJI.get(rarity, '')} {rarity})",
        value=_hp_bar(session.titan_hp, session.titan_max_hp),
        inline=False
    )
    embed.set_thumbnail(url=TITAN_IMAGES.get(session.titan_name, SURVEY_CORPS_ICON))
    return embed


async def setup(bot):
    await bot.add_cog(Battle(bot))
