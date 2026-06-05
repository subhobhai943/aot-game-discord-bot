"""Player vs Player titan battle system."""
from __future__ import annotations
import asyncio
import random
import discord
from discord.ext import commands
from utils.game_state import (
    GameState, PvPSession, TITAN_STATS, TITAN_IMAGES,
    RARITY_COLOR, RARITY_EMOJI, SURVEY_CORPS_ICON, pvp_titan_attack
)

BATTLE_TIMEOUT = 120   # seconds to accept a challenge
TURN_TIMEOUT   = 30    # seconds per turn

# ── HP bar helper ──────────────────────────────────────────────────────────
def _hp_bar(current: int, maximum: int, length: int = 10) -> str:
    filled = max(0, int((current / maximum) * length))
    bar    = "█" * filled + "░" * (length - filled)
    pct    = int((current / maximum) * 100)
    return f"`[{bar}]` {current}/{maximum} ({pct}%)"


def _battle_embed(session: PvPSession, log: list[str], c_name: str, o_name: str) -> discord.Embed:
    c_titan = session.challenger_titan
    o_titan = session.opponent_titan
    c_stats = TITAN_STATS.get(c_titan, {})
    o_stats = TITAN_STATS.get(o_titan, {})

    color = RARITY_COLOR.get(c_stats.get("rarity", "Common"), 0x5599FF)
    embed = discord.Embed(
        title=f"⚔️ PvP Battle — Round {session.round_num}",
        color=color
    )
    embed.add_field(
        name=f"🔴 {c_name} — {RARITY_EMOJI.get(c_stats.get('rarity','Common'),'')} {c_titan}",
        value=_hp_bar(session.challenger_hp, session.challenger_max),
        inline=False
    )
    embed.add_field(
        name=f"🔵 {o_name} — {RARITY_EMOJI.get(o_stats.get('rarity','Common'),'')} {o_titan}",
        value=_hp_bar(session.opponent_hp, session.opponent_max),
        inline=False
    )
    if log:
        embed.add_field(name="📜 Battle Log", value="\n".join(log[-4:]), inline=False)
    embed.set_thumbnail(url=TITAN_IMAGES.get(c_titan, SURVEY_CORPS_ICON))
    embed.set_footer(text="React ⚔️ Attack | 🛡️ Defend | 💥 Special")
    return embed


class PvP(commands.Cog):
    """Player vs Player battle commands."""

    def __init__(self, bot: commands.Bot):
        self.bot    = bot
        self._log: dict[str, list[str]] = {}   # session key -> log lines

    # ── >battle @user ──────────────────────────────────────────────────────
    @commands.command(name="battle", aliases=["fight", "pvp"])
    async def battle(self, ctx: commands.Context, opponent: discord.Member):
        """Challenge another player to a titan battle! Usage: >battle @user"""
        if opponent.bot or opponent == ctx.author:
            await ctx.send("❌ You can't battle a bot or yourself!")
            return

        c_player = GameState.get_player(str(ctx.author.id), ctx.author.display_name)
        o_player = GameState.get_player(str(opponent.id), opponent.display_name)

        if not c_player.active_titan:
            await ctx.send(f"❌ {ctx.author.mention}, you have no active titan! Catch one first with `>catch`, then set it with `>setactive <name>`.")
            return
        if not o_player.active_titan:
            await ctx.send(f"❌ {opponent.mention} has no active titan set yet!")
            return

        # Check not already in battle
        if GameState.get_pvp(str(ctx.author.id)):
            await ctx.send("❌ You're already in a battle!")
            return
        if GameState.get_pvp(str(opponent.id)):
            await ctx.send(f"❌ {opponent.mention} is already in a battle!")
            return

        # Send challenge
        c_titan  = c_player.active_titan
        o_titan  = o_player.active_titan
        c_stats  = TITAN_STATS.get(c_titan, {})
        o_stats  = TITAN_STATS.get(o_titan, {})

        challenge_embed = discord.Embed(
            title="⚔️ Battle Challenge!",
            description=(
                f"{ctx.author.mention} challenges {opponent.mention} to a titan battle!\n\n"
                f"🔴 **{ctx.author.display_name}** → {RARITY_EMOJI.get(c_stats.get('rarity','Common'),'')} **{c_titan}**\n"
                f"🔵 **{opponent.display_name}** → {RARITY_EMOJI.get(o_stats.get('rarity','Common'),'')} **{o_titan}**\n\n"
                f"{opponent.mention}, react with ✅ to accept or ❌ to decline!"
            ),
            color=0xFFAA00
        )
        challenge_embed.set_image(url=TITAN_IMAGES.get(c_titan, SURVEY_CORPS_ICON))
        msg = await ctx.send(embed=challenge_embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

        def check(reaction, user):
            return (
                user == opponent
                and str(reaction.emoji) in ("✅", "❌")
                and reaction.message.id == msg.id
            )

        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=BATTLE_TIMEOUT, check=check)
        except asyncio.TimeoutError:
            await ctx.send(f"⏰ {opponent.mention} didn't respond in time. Challenge cancelled.")
            return

        if str(reaction.emoji) == "❌":
            await ctx.send(f"❌ {opponent.mention} declined the battle challenge.")
            return

        # Start PvP
        session = GameState.start_pvp(
            str(ctx.author.id), str(opponent.id), c_titan, o_titan
        )
        session.channel_id = ctx.channel.id
        log_key = f"{ctx.author.id}_{opponent.id}"
        self._log[log_key] = ["⚔️ **Battle started!** May the strongest titan win!"]

        await self._run_battle(ctx, session, c_player, o_player, log_key)

    # ── Battle runner ──────────────────────────────────────────────────────
    async def _run_battle(
        self,
        ctx: commands.Context,
        session: PvPSession,
        c_player,
        o_player,
        log_key: str,
    ):
        channel = ctx.channel
        log     = self._log[log_key]
        c_name  = c_player.username
        o_name  = o_player.username
        move_emojis = {"⚔️": "attack", "🛡️": "defend", "💥": "special"}

        battle_msg = await channel.send(embed=_battle_embed(session, log, c_name, o_name))
        session.message_id = battle_msg.id
        for e in move_emojis:
            await battle_msg.add_reaction(e)

        defending: dict[str, bool] = {}

        while session.active:
            current_id  = session.current_turn
            current_obj = ctx.author if current_id == str(ctx.author.id) else ctx.message.guild.get_member(int(session.opponent_id))
            if current_obj is None:
                break

            turn_embed = _battle_embed(session, log, c_name, o_name)
            turn_embed.description = f"⏳ **{current_obj.display_name}'s turn!** React to attack! ({TURN_TIMEOUT}s)"
            await battle_msg.edit(embed=turn_embed)

            def react_check(reaction, user):
                return (
                    user.id == int(current_id)
                    and str(reaction.emoji) in move_emojis
                    and reaction.message.id == battle_msg.id
                )

            try:
                reaction, _ = await self.bot.wait_for("reaction_add", timeout=TURN_TIMEOUT, check=react_check)
                move = move_emojis[str(reaction.emoji)]
            except asyncio.TimeoutError:
                # Auto-attack on timeout
                move = "attack"
                log.append(f"⏰ {current_obj.display_name} ran out of time — auto-attack!")

            # Determine attacker/defender titans and HPs
            is_challenger = (current_id == session.challenger_id)
            atk_titan = session.challenger_titan if is_challenger else session.opponent_titan
            def_titan = session.opponent_titan   if is_challenger else session.challenger_titan

            if move == "defend":
                defending[current_id] = True
                log.append(f"🛡️ **{current_obj.display_name}**'s **{atk_titan}** takes a defensive stance!")
                dmg = 0
            elif move == "special":
                # Special: high damage, 25% miss
                if random.random() < 0.25:
                    dmg = 0
                    log.append(f"💥 **{current_obj.display_name}**'s **{atk_titan}** fires a Thunder Spear but MISSES!")
                else:
                    stats = TITAN_STATS.get(atk_titan, {"atk": 60})
                    dmg   = random.randint(stats["atk"], int(stats["atk"] * 1.5))
                    log.append(f"💥 **{current_obj.display_name}**'s **{atk_titan}** fires a Thunder Spear for **{dmg} DMG**!")
            else:
                dmg, missed, action = pvp_titan_attack(atk_titan, def_titan)
                # Halve damage if defender is defending
                opponent_id = session.opponent_id if is_challenger else session.challenger_id
                if defending.get(opponent_id):
                    dmg = dmg // 2
                    defending.pop(opponent_id, None)
                if missed:
                    log.append(f"⚔️ **{current_obj.display_name}**'s **{atk_titan}** {action} — MISS!")
                else:
                    log.append(f"⚔️ **{current_obj.display_name}**'s **{atk_titan}** {action} for **{dmg} DMG**!")

            # Apply damage
            if is_challenger:
                session.opponent_hp = max(0, session.opponent_hp - dmg)
            else:
                session.challenger_hp = max(0, session.challenger_hp - dmg)

            # Check win condition
            if session.challenger_hp <= 0 or session.opponent_hp <= 0:
                session.active = False
                break

            # Switch turn
            session.current_turn = (
                session.opponent_id if is_challenger else session.challenger_id
            )
            session.round_num += 1

            await battle_msg.edit(embed=_battle_embed(session, log, c_name, o_name))

        # ── Determine winner ───────────────────────────────────────────────
        if session.challenger_hp <= 0:
            winner_id, loser_id = session.opponent_id, session.challenger_id
        else:
            winner_id, loser_id = session.challenger_id, session.opponent_id

        winner_member = ctx.guild.get_member(int(winner_id))
        loser_member  = ctx.guild.get_member(int(loser_id))
        winner_player = GameState.get_player(winner_id, winner_member.display_name if winner_member else "?")
        loser_player  = GameState.get_player(loser_id,  loser_member.display_name  if loser_member  else "?")

        winner_player.wins   += 1
        winner_player.kills  += 1
        winner_player.coins  += 50
        winner_player.add_xp(100)
        loser_player.losses  += 1
        loser_player.add_xp(30)
        GameState.save_player(winner_player)
        GameState.save_player(loser_player)
        GameState.end_pvp(session)
        self._log.pop(log_key, None)

        win_titan  = session.challenger_titan if winner_id == session.challenger_id else session.opponent_titan
        win_stats  = TITAN_STATS.get(win_titan, {})

        result_embed = discord.Embed(
            title="🏆 Battle Over!",
            description=(
                f"**{winner_member.mention if winner_member else winner_id}** wins!\n"
                f"**{RARITY_EMOJI.get(win_stats.get('rarity','Common'),'')} {win_titan}** is victorious!\n\n"
                f"🏆 +1 Win | +50 Coins | +100 XP for {winner_member.display_name if winner_member else '?'}"
            ),
            color=0xFFAA00
        )
        result_embed.set_image(url=TITAN_IMAGES.get(win_titan, SURVEY_CORPS_ICON))
        result_embed.set_footer(text="Use >leaderboard to see the rankings!")
        await channel.send(embed=result_embed)

    # ── >profile ───────────────────────────────────────────────────────────
    @commands.command(name="profile", aliases=["p", "stats"])
    async def profile(self, ctx: commands.Context, member: discord.Member = None):
        """View a player's profile and stats. Usage: >profile [@user]"""
        target = member or ctx.author
        player = GameState.get_player(str(target.id), target.display_name)
        active_titan = player.active_titan or "None set"
        stats  = TITAN_STATS.get(active_titan, {})
        rarity = stats.get("rarity", "Common")

        embed = discord.Embed(
            title=f"🪖 {target.display_name}'s Profile",
            color=RARITY_COLOR.get(rarity, 0x5599FF)
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="🏅 Rank",         value=player.rank,               inline=True)
        embed.add_field(name="📈 Level",         value=player.level,              inline=True)
        embed.add_field(name="⚡ XP",            value=f"{player.xp}/{player.xp_needed}", inline=True)
        embed.add_field(name="🏆 Wins",          value=player.wins,               inline=True)
        embed.add_field(name="💀 Losses",        value=player.losses,             inline=True)
        embed.add_field(name="⚔️ Kill Count",    value=player.kills,              inline=True)
        embed.add_field(name="💰 Coins",         value=player.coins,              inline=True)
        embed.add_field(name="🗂️ Titans Owned",  value=player.total_titans(),     inline=True)
        embed.add_field(
            name="👹 Active Titan",
            value=f"{RARITY_EMOJI.get(rarity,'')} {active_titan}",
            inline=True
        )
        if active_titan != "None set":
            embed.set_image(url=TITAN_IMAGES.get(active_titan, SURVEY_CORPS_ICON))
        embed.set_footer(text="Use >collection to view all your titans!")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(PvP(bot))
