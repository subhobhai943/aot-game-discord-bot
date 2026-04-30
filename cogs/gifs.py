"""OwO-style AoT reaction GIF commands (prefix-based)."""

import discord
from discord.ext import commands
from utils.gifs import get_gif

REACTIONS: dict[str, tuple[str, str, str, str]] = {
    "hug":       ("hug",       "attack on titan hug",                 "🫂", "{author} hugs {target}!"),
    "pat":       ("pat",       "attack on titan pat",                 "🤚", "{author} pats {target}!"),
    "slap":      ("slap",      "attack on titan slap",                "👋", "{author} slaps {target}! 💥"),
    "bonk":      ("bonk",      "levi ackerman hit",                   "🔨", "{author} bonks {target}! 🔨"),
    "wave":      ("wave",      "attack on titan salute",              "👋", "{author} waves at {target}!"),
    "poke":      ("poke",      "attack on titan poke",                "👉", "{author} pokes {target}!"),
    "kiss":      ("kiss",      "eren mikasa",                         "💋", "{author} kisses {target}!"),
    "cry":       ("cry",       "attack on titan cry",                 "😢", "{author} is crying..."),
    "blush":     ("blush",     "mikasa blush",                        "😊", "{author} blushes at {target}!"),
    "bite":      ("bite",      "attack on titan bite",                "😬", "{author} bites {target}!"),
    "cuddle":    ("cuddle",    "attack on titan cuddle",              "🤗", "{author} cuddles {target}!"),
    "punch":     ("punch",     "attack on titan punch",               "👊", "{author} punches {target}! 💥"),
    "dance":     ("dance",     "attack on titan funny",               "💃", "{author} dances with {target}!"),
    "laugh":     ("laugh",     "attack on titan laugh",               "😂", "{author} laughs at {target}!"),
    "wink":      ("wink",      "attack on titan wink",                "😉", "{author} winks at {target}!"),
    "transform": ("transform", "eren titan transformation",           "⚡", "{author} transforms before {target}!"),
    "salute":    ("salute",    "survey corps salute",                 "🫡", "{author} salutes {target}! Sasageyo!"),
    "scream":    ("scream",    "eren yeager scream tatakae",          "🗣️", "{author} screams at {target}! TATAKAE!"),
    "charge":    ("charge",    "attack on titan charge scout regiment","🐎", "{author} charges toward {target}!"),
    "slice":     ("slice",     "levi ackerman slash",                 "🗡️", "{author} slices toward {target}!"),
    "yeager":    ("yeager",    "eren yeager tatakae",                 "🔥", "{author} goes full Yeager on {target}!"),
}

REACTION_COLORS: dict[str, discord.Color] = {
    "hug": discord.Color(0xFF91A4),
    "pat": discord.Color.teal(),
    "slap": discord.Color.red(),
    "bonk": discord.Color.orange(),
    "wave": discord.Color.blue(),
    "poke": discord.Color.purple(),
    "kiss": discord.Color.magenta(),
    "cry": discord.Color.dark_blue(),
    "blush": discord.Color.gold(),
    "bite": discord.Color.dark_red(),
    "cuddle": discord.Color.green(),
    "punch": discord.Color.red(),
    "dance": discord.Color.blurple(),
    "laugh": discord.Color(0xFFD700),
    "wink": discord.Color.teal(),
    "transform": discord.Color.dark_orange(),
    "salute": discord.Color.dark_gold(),
    "scream": discord.Color.dark_red(),
    "charge": discord.Color.dark_green(),
    "slice": discord.Color.light_grey(),
    "yeager": discord.Color.from_rgb(0, 200, 120),
}

OPTIONAL_TARGET = {"cry", "dance", "laugh", "transform", "scream", "charge"}


class Gifs(commands.Cog, name="🎭 Reactions"):
    """AoT-themed reaction GIF commands."""

    def __init__(self, bot):
        self.bot = bot

    async def _react(self, ctx: commands.Context, member: discord.Member | None, action: str):
        _, query, emoji, template = REACTIONS[action]
        needs_target = action not in OPTIONAL_TARGET

        if needs_target and member is None:
            p = ctx.prefix.strip()
            await ctx.send(f"❌ Please mention someone!\nExample: `{p} {action} @user`")
            return

        author = ctx.author.display_name
        target = member.display_name if member else "everyone"
        desc = template.format(author=author, target=target)
        gif_url = await get_gif(action, query)

        embed = discord.Embed(
            description=f"**{emoji} {desc}**",
            color=REACTION_COLORS.get(action, discord.Color.blurple()),
        )
        if gif_url:
            embed.set_image(url=gif_url)
        embed.set_footer(text=f"🪶 AoT Reactions • Requested by {author}")
        await ctx.send(embed=embed)

    @commands.command(name="hug")
    async def hug(self, ctx, member: discord.Member = None): await self._react(ctx, member, "hug")
    @commands.command(name="pat")
    async def pat(self, ctx, member: discord.Member = None): await self._react(ctx, member, "pat")
    @commands.command(name="slap")
    async def slap(self, ctx, member: discord.Member = None): await self._react(ctx, member, "slap")
    @commands.command(name="bonk")
    async def bonk(self, ctx, member: discord.Member = None): await self._react(ctx, member, "bonk")
    @commands.command(name="wave")
    async def wave(self, ctx, member: discord.Member = None): await self._react(ctx, member, "wave")
    @commands.command(name="poke")
    async def poke(self, ctx, member: discord.Member = None): await self._react(ctx, member, "poke")
    @commands.command(name="kiss")
    async def kiss(self, ctx, member: discord.Member = None): await self._react(ctx, member, "kiss")
    @commands.command(name="cry")
    async def cry(self, ctx, member: discord.Member = None): await self._react(ctx, member, "cry")
    @commands.command(name="blush")
    async def blush(self, ctx, member: discord.Member = None): await self._react(ctx, member, "blush")
    @commands.command(name="bite")
    async def bite(self, ctx, member: discord.Member = None): await self._react(ctx, member, "bite")
    @commands.command(name="cuddle")
    async def cuddle(self, ctx, member: discord.Member = None): await self._react(ctx, member, "cuddle")
    @commands.command(name="punch")
    async def punch(self, ctx, member: discord.Member = None): await self._react(ctx, member, "punch")
    @commands.command(name="dance")
    async def dance(self, ctx, member: discord.Member = None): await self._react(ctx, member, "dance")
    @commands.command(name="laugh")
    async def laugh(self, ctx, member: discord.Member = None): await self._react(ctx, member, "laugh")
    @commands.command(name="wink")
    async def wink(self, ctx, member: discord.Member = None): await self._react(ctx, member, "wink")
    @commands.command(name="transform", aliases=["titan"])
    async def transform(self, ctx, member: discord.Member = None): await self._react(ctx, member, "transform")
    @commands.command(name="salute")
    async def salute(self, ctx, member: discord.Member = None): await self._react(ctx, member, "salute")
    @commands.command(name="scream")
    async def scream(self, ctx, member: discord.Member = None): await self._react(ctx, member, "scream")
    @commands.command(name="charge")
    async def charge(self, ctx, member: discord.Member = None): await self._react(ctx, member, "charge")
    @commands.command(name="slice")
    async def slice(self, ctx, member: discord.Member = None): await self._react(ctx, member, "slice")
    @commands.command(name="yeager", aliases=["tatakae"])
    async def yeager(self, ctx, member: discord.Member = None): await self._react(ctx, member, "yeager")

    @commands.command(name="reactions", aliases=["gifhelp", "gifcmds"])
    async def list_reactions(self, ctx):
        p = ctx.prefix.strip()
        embed = discord.Embed(
            title="🎭 AoT Reaction Commands",
            description=(
                f"Use `{p} <command> @user` for animated AoT GIFs!\n"
                f"Uses **Giphy public key**, **Tenor public key**, and curated AoT fallbacks."
            ),
            color=discord.Color.dark_red(),
        )
        for act, (_, _, emoji, _) in REACTIONS.items():
            embed.add_field(name=f"{emoji} `{p} {act}`", value=f"AoT **{act}** GIF", inline=True)
        embed.set_footer(text="🪶 AoT Game Bot • AoT-only GIF priority enabled")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Gifs(bot))
