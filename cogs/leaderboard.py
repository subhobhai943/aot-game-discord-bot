"""Leaderboard cog — rankings by wins, level, collection size, and coins."""
from __future__ import annotations
import discord
from discord.ext import commands
from utils.game_state import GameState, SURVEY_CORPS_ICON, RARITY_EMOJI, TITAN_STATS


MEDALS = ["🥇", "🥈", "🥉"]


def _rank_medal(pos: int) -> str:
    return MEDALS[pos] if pos < len(MEDALS) else f"#{pos + 1}"


class Leaderboard(commands.Cog):
    """Leaderboard and ranking commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── >leaderboard ───────────────────────────────────────────────────────
    @commands.command(name="leaderboard", aliases=["lb", "top", "rank"])
    async def leaderboard(self, ctx: commands.Context, category: str = "wins"):
        """Show leaderboard. Categories: wins | level | titans | coins. Usage: >leaderboard [wins|level|titans|coins]"""
        category = category.lower()
        valid = ("wins", "level", "titans", "coins")
        if category not in valid:
            await ctx.send(f"❌ Invalid category. Choose from: `{'`, `'.join(valid)}`")
            return

        players = await GameState.all_players()
        if not players:
            await ctx.send("No players found yet! Start playing with `>catch`!")
            return

        # Sort
        if category == "wins":
            sorted_p = sorted(players, key=lambda p: (p.wins, p.kills, p.level), reverse=True)
            title    = "🏆 Battle Wins Leaderboard"
            val_fn   = lambda p: f"🏆 {p.wins}W / 💀 {p.losses}L"
        elif category == "level":
            sorted_p = sorted(players, key=lambda p: (p.level, p.xp), reverse=True)
            title    = "📈 Level Leaderboard"
            val_fn   = lambda p: f"Level {p.level} — {p.rank} ({p.xp}/{p.xp_needed} XP)"
        elif category == "titans":
            sorted_p = sorted(players, key=lambda p: p.total_titans(), reverse=True)
            title    = "🗂️ Titan Collection Leaderboard"
            val_fn   = lambda p: f"{p.total_titans()} titans | Best: {p.best_titan() or 'None'}"
        else:  # coins
            sorted_p = sorted(players, key=lambda p: p.coins, reverse=True)
            title    = "💰 Richest Scouts Leaderboard"
            val_fn   = lambda p: f"💰 {p.coins} coins"

        top    = sorted_p[:10]
        embed  = discord.Embed(title=title, color=0xFFAA00)
        embed.set_thumbnail(url=SURVEY_CORPS_ICON)

        lines = []
        for i, player in enumerate(top):
            medal   = _rank_medal(i)
            active  = f" ({RARITY_EMOJI.get(TITAN_STATS.get(player.active_titan, {}).get('rarity',''), '')} {player.active_titan})" if player.active_titan else ""
            lines.append(f"{medal} **{player.username}**{active} — {val_fn(player)}")

        embed.description = "\n".join(lines) if lines else "No data yet!"

        # Show caller's rank
        caller = await GameState.get_player(str(ctx.author.id), ctx.author.display_name)
        try:
            caller_rank = sorted_p.index(caller) + 1
            embed.set_footer(text=f"Your rank: #{caller_rank} out of {len(sorted_p)} scouts")
        except ValueError:
            embed.set_footer(text=f"Total scouts: {len(sorted_p)}")

        # Add navigation hint
        embed.add_field(
            name="📊 Other Rankings",
            value="`>lb wins` | `>lb level` | `>lb titans` | `>lb coins`",
            inline=False
        )
        await ctx.send(embed=embed)

    # ── >rank @user ────────────────────────────────────────────────────────
    @commands.command(name="myrank", aliases=["ranking"])
    async def myrank(self, ctx: commands.Context, member: discord.Member = None):
        """Check your rank across all categories. Usage: >myrank [@user]"""
        target = member or ctx.author
        player = await GameState.get_player(str(target.id), target.display_name)
        players = await GameState.all_players()

        wins_rank   = sorted(players, key=lambda p: (p.wins, p.kills),      reverse=True)
        level_rank  = sorted(players, key=lambda p: (p.level, p.xp),        reverse=True)
        titans_rank = sorted(players, key=lambda p: p.total_titans(),        reverse=True)
        coins_rank  = sorted(players, key=lambda p: p.coins,                 reverse=True)

        def pos(lst):
            try:
                return f"#{lst.index(player) + 1}"
            except ValueError:
                return "N/A"

        embed = discord.Embed(
            title=f"📊 {target.display_name}'s Rankings",
            color=0x5599FF
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="🏆 Battle Wins",        value=f"{pos(wins_rank)} ({player.wins}W)",             inline=True)
        embed.add_field(name="📈 Level",              value=f"{pos(level_rank)} (Lv.{player.level})",         inline=True)
        embed.add_field(name="🗂️ Collection Size",   value=f"{pos(titans_rank)} ({player.total_titans()})",   inline=True)
        embed.add_field(name="💰 Coins",              value=f"{pos(coins_rank)} ({player.coins})",             inline=True)
        embed.add_field(name="⚔️ Kill Count",         value=player.kills,                                      inline=True)
        embed.add_field(name="🏅 Scout Rank",         value=player.rank,                                       inline=True)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Leaderboard(bot))
