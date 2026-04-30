"""OwO-style AoT reaction GIF commands (prefix-based).

Examples  (prefix = 'aot'):
    aot hug @user
    aot slap @user
    aot cry
    aot reactions   ← shows the full list
"""
import discord
from discord.ext import commands
from utils.gifs import get_gif

# (nekos_action, tenor_query, emoji, description_template)
REACTIONS: dict[str, tuple[str, str, str, str]] = {
    "hug":    ("hug",    "hug embrace",       "\U0001fac2", "{author} hugs {target}!"),
    "pat":    ("pat",    "pat head",          "\U0001f91a", "{author} pats {target}!"),
    "slap":   ("slap",   "slap",              "\U0001f44b", "{author} slaps {target}! \U0001f4a5"),
    "bonk":   ("bonk",   "bonk hit",          "\U0001f528", "{author} bonks {target}! \U0001f528"),
    "wave":   ("wave",   "wave hello",        "\U0001f44b", "{author} waves at {target}!"),
    "poke":   ("poke",   "poke finger",       "\U0001f449", "{author} pokes {target}!"),
    "kiss":   ("kiss",   "kiss lips",         "\U0001f48b", "{author} kisses {target}!"),
    "cry":    ("cry",    "cry sad",           "\U0001f622", "{author} is crying..."),
    "blush":  ("blush",  "blush shy",         "\U0001f60a", "{author} blushes at {target}!"),
    "bite":   ("bite",   "bite neck",         "\U0001f62c", "{author} bites {target}!"),
    "cuddle": ("cuddle", "cuddle warm",       "\U0001f917", "{author} cuddles {target}!"),
    "punch":  ("punch",  "punch attack",      "\U0001f44a", "{author} punches {target}! \U0001f4a5"),
    "dance":  ("dance",  "dance celebrate",   "\U0001f483", "{author} dances with {target}!"),
    "laugh":  ("laugh",  "laugh funny",       "\U0001f602", "{author} laughs at {target}!"),
    "wink":   ("wink",   "wink flirt",        "\U0001f609", "{author} winks at {target}!"),
}

REACTION_COLORS: dict[str, discord.Color] = {
    "hug":    discord.Color(0xFF91A4),
    "pat":    discord.Color.teal(),
    "slap":   discord.Color.red(),
    "bonk":   discord.Color.orange(),
    "wave":   discord.Color.blue(),
    "poke":   discord.Color.purple(),
    "kiss":   discord.Color.magenta(),
    "cry":    discord.Color.dark_blue(),
    "blush":  discord.Color.gold(),
    "bite":   discord.Color.dark_red(),
    "cuddle": discord.Color.green(),
    "punch":  discord.Color.red(),
    "dance":  discord.Color.blurple(),
    "laugh":  discord.Color(0xFFD700),
    "wink":   discord.Color.teal(),
}

# Commands where mentioning a target is optional
OPTIONAL_TARGET = {"cry", "dance", "laugh"}


class Gifs(commands.Cog, name="\U0001f3ad Reactions"):
    """AoT-themed reaction GIF commands \u2014 like OwO bot!"""

    def __init__(self, bot):
        self.bot = bot

    async def _react(self, ctx: commands.Context, member: discord.Member | None, action: str):
        """Core reaction handler shared by every command."""
        nekos_act, tenor_q, emoji, template = REACTIONS[action]
        needs_target = action not in OPTIONAL_TARGET

        if needs_target and member is None:
            p = ctx.prefix.strip()
            await ctx.send(f"\u274c Please mention someone!\nExample: `{p} {action} @user`")
            return

        author = ctx.author.display_name
        target = member.display_name if member else "everyone"
        desc = template.format(author=author, target=target)

        gif_url = await get_gif(nekos_act, tenor_q)

        embed = discord.Embed(
            description=f"**{emoji} {desc}**",
            color=REACTION_COLORS.get(action, discord.Color.blurple()),
        )
        if gif_url:
            embed.set_image(url=gif_url)
        embed.set_footer(text=f"\U0001fab5 AoT Reactions  \u2022  Requested by {author}")
        await ctx.send(embed=embed)

    # ── Reaction commands ──────────────────────────────────────────────────────

    @commands.command(name="hug")
    async def hug(self, ctx, member: discord.Member = None):
        """Hug someone with an AoT GIF! Usage: `{prefix} hug @user`"""
        await self._react(ctx, member, "hug")

    @commands.command(name="pat")
    async def pat(self, ctx, member: discord.Member = None):
        """Pat someone! Usage: `{prefix} pat @user`"""
        await self._react(ctx, member, "pat")

    @commands.command(name="slap")
    async def slap(self, ctx, member: discord.Member = None):
        """Slap someone! Usage: `{prefix} slap @user`"""
        await self._react(ctx, member, "slap")

    @commands.command(name="bonk")
    async def bonk(self, ctx, member: discord.Member = None):
        """Bonk someone! Usage: `{prefix} bonk @user`"""
        await self._react(ctx, member, "bonk")

    @commands.command(name="wave")
    async def wave(self, ctx, member: discord.Member = None):
        """Wave at someone! Usage: `{prefix} wave @user`"""
        await self._react(ctx, member, "wave")

    @commands.command(name="poke")
    async def poke(self, ctx, member: discord.Member = None):
        """Poke someone! Usage: `{prefix} poke @user`"""
        await self._react(ctx, member, "poke")

    @commands.command(name="kiss")
    async def kiss(self, ctx, member: discord.Member = None):
        """Kiss someone! Usage: `{prefix} kiss @user`"""
        await self._react(ctx, member, "kiss")

    @commands.command(name="cry")
    async def cry(self, ctx, member: discord.Member = None):
        """Cry alone or with someone! Usage: `{prefix} cry`"""
        await self._react(ctx, member, "cry")

    @commands.command(name="blush")
    async def blush(self, ctx, member: discord.Member = None):
        """Blush at someone! Usage: `{prefix} blush @user`"""
        await self._react(ctx, member, "blush")

    @commands.command(name="bite")
    async def bite(self, ctx, member: discord.Member = None):
        """Bite someone like a Titan! Usage: `{prefix} bite @user`"""
        await self._react(ctx, member, "bite")

    @commands.command(name="cuddle")
    async def cuddle(self, ctx, member: discord.Member = None):
        """Cuddle with someone! Usage: `{prefix} cuddle @user`"""
        await self._react(ctx, member, "cuddle")

    @commands.command(name="punch")
    async def punch(self, ctx, member: discord.Member = None):
        """Punch someone! Usage: `{prefix} punch @user`"""
        await self._react(ctx, member, "punch")

    @commands.command(name="dance")
    async def dance(self, ctx, member: discord.Member = None):
        """Dance! Usage: `{prefix} dance` or `{prefix} dance @user`"""
        await self._react(ctx, member, "dance")

    @commands.command(name="laugh")
    async def laugh(self, ctx, member: discord.Member = None):
        """Laugh! Usage: `{prefix} laugh` or `{prefix} laugh @user`"""
        await self._react(ctx, member, "laugh")

    @commands.command(name="wink")
    async def wink(self, ctx, member: discord.Member = None):
        """Wink at someone! Usage: `{prefix} wink @user`"""
        await self._react(ctx, member, "wink")

    # ── Help listing ──────────────────────────────────────────────────────────────

    @commands.command(name="reactions", aliases=["gifhelp", "gifcmds"])
    async def list_reactions(self, ctx):
        """Show all AoT reaction GIF commands."""
        p = ctx.prefix.strip()
        embed = discord.Embed(
            title="\U0001f3ad AoT Reaction Commands",
            description=(
                f"Use `{p} <command> @user` for animated AoT GIFs!\n"
                f"Powered by **Tenor** (AoT GIFs) & **nekos.best** (fallback)."
            ),
            color=discord.Color.dark_red(),
        )
        for act, (_, _, emoji, _) in REACTIONS.items():
            embed.add_field(
                name=f"{emoji} `{p} {act}`",
                value=f"AoT **{act}** GIF",
                inline=True,
            )
        embed.set_footer(text="\U0001fab5 AoT Game Bot  \u2022  Set your Tenor API key in .env for AoT-specific GIFs")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Gifs(bot))
