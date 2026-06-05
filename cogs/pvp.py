"""Player vs Player titan battle system.
Command: Aot battle @user
"""
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


def _hp_bar(current: int, maximum: int, length: int = 10) -> str:
    filled = max(0, int((current / maximum) * length))
    bar    = "\u2588" * filled + "\u2591" * (length - filled)
    pct    = int((current / maximum) * 100)
    return f"`[{bar}]` {current}/{maximum} ({pct}%)"


def _battle_embed(session: PvPSession, log: list[str], c_name: str, o_name: str) -> discord.Embed:
    c_titan = session.challenger_titan
    o_titan = session.opponent_titan
    c_stats = TITAN_STATS.get(c_titan, {})
    o_stats = TITAN_STATS.get(o_titan, {})
    color   = RARITY_COLOR.get(c_stats.get("rarity", "Common"), 0x5599FF)
    embed   = discord.Embed(
        title=f"\u2694\ufe0f PvP Battle \u2014 Round {session.round_num}",
        color=color
    )
    embed.add_field(
        name=f"\U0001f534 {c_name} \u2014 {RARITY_EMOJI.get(c_stats.get('rarity','Common'),'')} {c_titan}",
        value=_hp_bar(session.challenger_hp, session.challenger_max),
        inline=False
    )
    embed.add_field(
        name=f"\U0001f535 {o_name} \u2014 {RARITY_EMOJI.get(o_stats.get('rarity','Common'),'')} {o_titan}",
        value=_hp_bar(session.opponent_hp, session.opponent_max),
        inline=False
    )
    if log:
        embed.add_field(name="\U0001f4dc Battle Log", value="\n".join(log[-4:]), inline=False)
    embed.set_thumbnail(url=TITAN_IMAGES.get(c_titan, SURVEY_CORPS_ICON))
    embed.set_footer(text="React \u2694\ufe0f Attack | \U0001f6e1\ufe0f Defend | \U0001f4a5 Special")
    return embed


class PvP(commands.Cog):
    """Player vs Player battle commands."""

    def __init__(self, bot: commands.Bot):
        self.bot  = bot
        self._log: dict[str, list[str]] = {}

    # ── Aot battle @user ───────────────────────────────────────────────────
    @commands.command(name="battle", aliases=["pvp", "vs", "challenge"])
    async def battle(self, ctx: commands.Context, opponent: discord.Member):
        """
        Challenge another player to a titan PvP battle!
        Usage: Aot battle @user
        Both players must have an active titan set (use Aot setactive <titan>).
        """
        if opponent.bot or opponent == ctx.author:
            await ctx.send("\u274c You can't battle a bot or yourself!")
            return

        c_player = GameState.get_player(str(ctx.author.id), ctx.author.display_name)
        o_player = GameState.get_player(str(opponent.id), opponent.display_name)

        prefix = ctx.prefix or "Aot "

        if not c_player.active_titan:
            await ctx.send(
                f"\u274c {ctx.author.mention}, you have no active titan!\n"
                f"Catch one with `{prefix}catch`, then equip it with `{prefix}setactive <name>`."
            )
            return
        if not o_player.active_titan:
            await ctx.send(
                f"\u274c {opponent.mention} has no active titan set yet!\n"
                f"They need to use `{prefix}setactive <name>` first."
            )
            return

        if GameState.get_pvp(str(ctx.author.id)):
            await ctx.send("\u274c You're already in a PvP battle!")
            return
        if GameState.get_pvp(str(opponent.id)):
            await ctx.send(f"\u274c {opponent.mention} is already in a battle!")
            return

        c_titan = c_player.active_titan
        o_titan = o_player.active_titan
        c_stats = TITAN_STATS.get(c_titan, {})
        o_stats = TITAN_STATS.get(o_titan, {})

        challenge_embed = discord.Embed(
            title="\u2694\ufe0f Titan Battle Challenge!",
            description=(
                f"{ctx.author.mention} challenges {opponent.mention} to a titan battle!\n\n"
                f"\U0001f534 **{ctx.author.display_name}** \u2192 "
                f"{RARITY_EMOJI.get(c_stats.get('rarity','Common'),'')} **{c_titan}**\n"
                f"\U0001f535 **{opponent.display_name}** \u2192 "
                f"{RARITY_EMOJI.get(o_stats.get('rarity','Common'),'')} **{o_titan}**\n\n"
                f"{opponent.mention}, react with \u2705 to accept or \u274c to decline!"
            ),
            color=0xFFAA00
        )
        challenge_embed.set_thumbnail(url=TITAN_IMAGES.get(c_titan, SURVEY_CORPS_ICON))
        msg = await ctx.send(embed=challenge_embed)
        await msg.add_reaction("\u2705")
        await msg.add_reaction("\u274c")

        def check(reaction, user):
            return (
                user == opponent
                and str(reaction.emoji) in ("\u2705", "\u274c")
                and reaction.message.id == msg.id
            )

        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=BATTLE_TIMEOUT, check=check)
        except asyncio.TimeoutError:
            await ctx.send(f"\u23f0 {opponent.mention} didn't respond in time. Challenge cancelled.")
            return

        if str(reaction.emoji) == "\u274c":
            await ctx.send(f"\u274c {opponent.mention} declined the battle challenge.")
            return

        # Start session
        session         = GameState.start_pvp(str(ctx.author.id), str(opponent.id), c_titan, o_titan)
        session.channel_id = ctx.channel.id
        log_key         = f"{ctx.author.id}_{opponent.id}"
        self._log[log_key] = ["\u2694\ufe0f **Battle started!** May the strongest titan win!"]

        await self._run_battle(ctx, session, c_player, o_player, log_key)

    # ── Turn-based battle loop ─────────────────────────────────────────────
    async def _run_battle(
        self,
        ctx: commands.Context,
        session: PvPSession,
        c_player,
        o_player,
        log_key: str,
    ):
        channel     = ctx.channel
        log         = self._log[log_key]
        c_name      = c_player.username
        o_name      = o_player.username
        move_emojis = {"\u2694\ufe0f": "attack", "\U0001f6e1\ufe0f": "defend", "\U0001f4a5": "special"}

        battle_msg = await channel.send(embed=_battle_embed(session, log, c_name, o_name))
        session.message_id = battle_msg.id
        for e in move_emojis:
            await battle_msg.add_reaction(e)

        defending: dict[str, bool] = {}

        while session.active:
            current_id  = session.current_turn
            current_obj = ctx.guild.get_member(int(current_id))
            if current_obj is None:
                break

            turn_embed = _battle_embed(session, log, c_name, o_name)
            turn_embed.description = (
                f"\u23f3 **{current_obj.display_name}'s turn!** "
                f"React to choose your move! ({TURN_TIMEOUT}s)"
            )
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
                move = "attack"
                log.append(f"\u23f0 {current_obj.display_name} timed out \u2014 auto-attack!")

            is_challenger = (current_id == session.challenger_id)
            atk_titan     = session.challenger_titan if is_challenger else session.opponent_titan
            def_titan     = session.opponent_titan   if is_challenger else session.challenger_titan
            opponent_id   = session.opponent_id if is_challenger else session.challenger_id

            if move == "defend":
                defending[current_id] = True
                log.append(f"\U0001f6e1\ufe0f **{current_obj.display_name}**'s **{atk_titan}** defends!")
                dmg = 0
            elif move == "special":
                if random.random() < 0.25:
                    dmg = 0
                    log.append(f"\U0001f4a5 **{current_obj.display_name}** fires Thunder Spear \u2014 MISS!")
                else:
                    stats = TITAN_STATS.get(atk_titan, {"atk": 60})
                    dmg   = random.randint(stats["atk"], int(stats["atk"] * 1.5))
                    log.append(f"\U0001f4a5 **{current_obj.display_name}** fires Thunder Spear for **{dmg} DMG**!")
            else:
                dmg, missed, action = pvp_titan_attack(atk_titan, def_titan)
                if defending.get(opponent_id):
                    dmg = dmg // 2
                    defending.pop(opponent_id, None)
                if missed:
                    log.append(f"\u2694\ufe0f **{current_obj.display_name}**'s **{atk_titan}** {action} \u2014 MISS!")
                else:
                    log.append(f"\u2694\ufe0f **{current_obj.display_name}**'s **{atk_titan}** {action} for **{dmg} DMG**!")

            if is_challenger:
                session.opponent_hp = max(0, session.opponent_hp - dmg)
            else:
                session.challenger_hp = max(0, session.challenger_hp - dmg)

            if session.challenger_hp <= 0 or session.opponent_hp <= 0:
                session.active = False
                break

            session.current_turn = opponent_id
            session.round_num   += 1
            await battle_msg.edit(embed=_battle_embed(session, log, c_name, o_name))

        # ── Result ─────────────────────────────────────────────────────────
        if session.challenger_hp <= 0:
            winner_id, loser_id = session.opponent_id, session.challenger_id
        else:
            winner_id, loser_id = session.challenger_id, session.opponent_id

        winner_member = ctx.guild.get_member(int(winner_id))
        loser_member  = ctx.guild.get_member(int(loser_id))
        w_player = GameState.get_player(winner_id, winner_member.display_name if winner_member else "?")
        l_player = GameState.get_player(loser_id,  loser_member.display_name  if loser_member  else "?")

        w_player.wins  += 1; w_player.kills += 1; w_player.coins += 50; w_player.add_xp(100)
        l_player.losses += 1; l_player.add_xp(30)
        GameState.save_player(w_player)
        GameState.save_player(l_player)
        GameState.end_pvp(session)
        self._log.pop(log_key, None)

        win_titan = session.challenger_titan if winner_id == session.challenger_id else session.opponent_titan
        win_stats = TITAN_STATS.get(win_titan, {})
        prefix    = ctx.prefix or "Aot "

        result_embed = discord.Embed(
            title="\U0001f3c6 Battle Over!",
            description=(
                f"{winner_member.mention if winner_member else winner_id} wins!\n"
                f"**{RARITY_EMOJI.get(win_stats.get('rarity','Common'),'')} {win_titan}** is victorious!\n\n"
                f"\U0001f3c6 +1 Win | +50 Coins | +100 XP for **{w_player.username}**\n"
                f"\U0001f4aa +30 XP for **{l_player.username}** \u2014 keep fighting!"
            ),
            color=0xFFAA00
        )
        result_embed.set_image(url=TITAN_IMAGES.get(win_titan, SURVEY_CORPS_ICON))
        result_embed.set_footer(text=f"Use {prefix}leaderboard to see the rankings!")
        await channel.send(embed=result_embed)


async def setup(bot):
    await bot.add_cog(PvP(bot))
