"""AoT reaction & combat GIF commands (prefix-based)."""

import discord
from discord.ext import commands
from utils.gifs import get_gif

REACTIONS: dict[str, tuple[str, str, str, str]] = {
    # ── Social reactions ─────────────────────────────────────────────
    "hug":           ("hug",           "attack on titan hug anime",                     "🤗", "{author} hugs {target}!"),
    "pat":           ("pat",           "attack on titan pat anime",                     "🫱", "{author} pats {target}!"),
    "slap":          ("slap",          "attack on titan slap anime",                    "👋", "{author} slaps {target}! 💥"),
    "bonk":          ("bonk",          "levi ackerman hit anime",                       "🔨", "{author} bonks {target}! 🔨"),
    "wave":          ("wave",          "anime wave hello friendly",                     "👋", "{author} waves at {target}!"),
    "poke":          ("poke",          "attack on titan poke anime",                    "👉", "{author} pokes {target}!"),
    "kiss":          ("kiss",          "eren mikasa kiss anime",                        "💋", "{author} kisses {target}!"),
    "cry":           ("cry",           "attack on titan cry anime",                     "😢", "{author} is crying..."),
    "blush":         ("blush",         "mikasa blush anime",                            "😊", "{author} blushes at {target}!"),
    "bite":          ("bite",          "attack on titan bite anime",                    "😬", "{author} bites {target}!"),
    "cuddle":        ("cuddle",        "attack on titan cuddle anime",                  "🤗", "{author} cuddles {target}!"),
    "dance":         ("dance",         "attack on titan funny dance",                   "💃", "{author} dances with {target}!"),
    "laugh":         ("laugh",         "attack on titan laugh anime",                   "😂", "{author} laughs at {target}!"),
    "wink":          ("wink",          "attack on titan wink anime",                    "😉", "{author} winks at {target}!"),
    # ── Combat reactions ────────────────────────────────────────────
    "punch":         ("punch",         "attack on titan punch anime",                   "👊", "{author} punches {target}! 💥"),
    "transform":     ("transform",     "eren titan transformation attack on titan",      "⚡",   "{author} transforms before {target}!"),
    "salute":        ("salute",        "survey corps salute attack on titan",            "🫱", "{author} salutes {target}! Sasageyo!"),
    "scream":        ("scream",        "eren yeager scream tatakae attack on titan",     "🗣️", "{author} screams at {target}! TATAKAE!"),
    "charge":        ("charge",        "attack on titan charge scout regiment",          "🐎", "{author} charges toward {target}!"),
    "slice":         ("slice",         "levi ackerman slash blade attack on titan",      "🗡️", "{author} slices toward {target}!"),
    "yeager":        ("yeager",        "eren yeager tatakae attack on titan",            "🔥", "{author} goes full Yeager on {target}!"),
    # ── NEW: AoT Combat & Special commands ──────────────────────────────
    "kill":          ("kill",          "levi ackerman kill titan attack on titan",       "☠️",  "{author} eliminates {target}! *They never saw it coming.*"),
    "odm":           ("odm",           "ODM gear swing attack on titan survey corps",    "🪝", "{author} swings past {target} on ODM gear!"),
    "thunder_spear": ("thunder_spear", "thunder spear attack on titan explosion",        "💥", "{author} fires a Thunder Spear at {target}! BOOM! 💥"),
    "nape":          ("nape",          "nape slash titan attack on titan kill",          "⚔️",  "{author} goes for the nape of {target}!"),
    "titan_eat":     ("titan_eat",     "titan eating attack on titan horror",            "😱", "{target} gets eaten by a Titan — {author} watches in horror!"),
    "rumble":        ("rumble",        "the rumbling attack on titan titans march",       "🌍", "{author} unleashes THE RUMBLING upon {target}! *The earth shakes.*"),
    "levi_kick":     ("levi_kick",     "levi ackerman kick attack on titan",             "🥾", "{author} delivers a Levi special kick to {target}!"),
    "founding":      ("founding",      "founding titan eren attack on titan colossal",   "👺", "{author} awakens the Founding Titan before {target}! *Bow down.*"),
    "scout":         ("scout",         "survey corps scouts running attack on titan",    "🍀", "{author} leads the Scout Regiment charge at {target}!"),
    "omni":          ("omni",          "omnidirectional mobility gear attack on titan",  "🔸", "{author} moves at godspeed and vanishes past {target}!"),
    "wall_break":    ("wall_break",    "colossal titan wall break attack on titan",      "💣", "{author} breaks through the wall protecting {target}!"),
    "colossal":      ("colossal",      "colossal titan attack on titan armin",           "⬆️",  "{author} rises as the Colossal Titan before {target}!"),
    "war_hammer":    ("war_hammer",    "war hammer titan attack on titan",               "🔨", "{author} summons the War Hammer Titan against {target}!"),
    "armored":       ("armored",       "armored titan reiner attack on titan",           "🛡️", "{author} goes Armored Titan mode on {target}!"),
    "freedom":       ("freedom",       "attack on titan wings of freedom survey corps",  "🦅", "{author} and {target} spread their wings — *fly free, soldiers!*"),
}

REACTION_COLORS: dict[str, discord.Color] = {
    # Social
    "hug":          discord.Color(0xFF91A4),
    "pat":          discord.Color.teal(),
    "slap":         discord.Color.red(),
    "bonk":         discord.Color.orange(),
    "wave":         discord.Color.blue(),
    "poke":         discord.Color.purple(),
    "kiss":         discord.Color.magenta(),
    "cry":          discord.Color.dark_blue(),
    "blush":        discord.Color.gold(),
    "bite":         discord.Color.dark_red(),
    "cuddle":       discord.Color.green(),
    "dance":        discord.Color.blurple(),
    "laugh":        discord.Color(0xFFD700),
    "wink":         discord.Color.teal(),
    # Combat
    "punch":        discord.Color.red(),
    "transform":    discord.Color.dark_orange(),
    "salute":       discord.Color.dark_gold(),
    "scream":       discord.Color.dark_red(),
    "charge":       discord.Color.dark_green(),
    "slice":        discord.Color.light_grey(),
    "yeager":       discord.Color.from_rgb(0, 200, 120),
    # New AoT
    "kill":         discord.Color.from_rgb(30, 30, 30),
    "odm":          discord.Color.from_rgb(50, 120, 200),
    "thunder_spear":discord.Color.from_rgb(255, 140, 0),
    "nape":         discord.Color.from_rgb(180, 20, 20),
    "titan_eat":    discord.Color.from_rgb(100, 0, 0),
    "rumble":       discord.Color.from_rgb(80, 60, 40),
    "levi_kick":    discord.Color.from_rgb(90, 90, 90),
    "founding":     discord.Color.from_rgb(160, 0, 255),
    "scout":        discord.Color.from_rgb(0, 160, 80),
    "omni":         discord.Color.from_rgb(30, 180, 230),
    "wall_break":   discord.Color.from_rgb(200, 100, 0),
    "colossal":     discord.Color.from_rgb(255, 80, 0),
    "war_hammer":   discord.Color.from_rgb(220, 220, 220),
    "armored":      discord.Color.from_rgb(160, 140, 100),
    "freedom":      discord.Color.from_rgb(100, 160, 255),
}

# Commands that don't strictly require a target
OPTIONAL_TARGET = {
    "cry", "dance", "laugh", "transform", "scream", "charge",
    "founding", "scout", "rumble", "freedom", "colossal",
}


class Gifs(commands.Cog, name="🎭 Reactions"):
    """AoT-themed reaction & combat GIF commands."""

    def __init__(self, bot):
        self.bot = bot

    async def _react(self, ctx: commands.Context, member: discord.Member | None, action: str):
        _, query, emoji, template = REACTIONS[action]
        needs_target = action not in OPTIONAL_TARGET

        if needs_target and member is None:
            p = ctx.prefix.strip()
            await ctx.send(f"❌ Please mention someone!\nExample: `{p}{action} @user`")
            return

        author = ctx.author.display_name
        target = member.display_name if member else "the battlefield"
        desc = template.format(author=author, target=target)
        gif_url = await get_gif(action, query)

        embed = discord.Embed(
            description=f"**{emoji} {desc}**",
            color=REACTION_COLORS.get(action, discord.Color.dark_red()),
        )
        if gif_url:
            embed.set_image(url=gif_url)
        embed.set_footer(text=f"🪝 AoT Reactions • Requested by {author}")
        await ctx.send(embed=embed)

    # ── Social ───────────────────────────────────────────────────────────
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
    @commands.command(name="dance")
    async def dance(self, ctx, member: discord.Member = None): await self._react(ctx, member, "dance")
    @commands.command(name="laugh")
    async def laugh(self, ctx, member: discord.Member = None): await self._react(ctx, member, "laugh")
    @commands.command(name="wink")
    async def wink(self, ctx, member: discord.Member = None): await self._react(ctx, member, "wink")

    # ── Original combat ────────────────────────────────────────────────
    @commands.command(name="punch")
    async def punch(self, ctx, member: discord.Member = None): await self._react(ctx, member, "punch")
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

    # ── NEW: AoT combat & special ─────────────────────────────────────────
    @commands.command(name="kill", aliases=["eliminate", "slay"])
    async def kill(self, ctx, member: discord.Member = None): await self._react(ctx, member, "kill")

    @commands.command(name="odm", aliases=["gear", "odmgear"])
    async def odm(self, ctx, member: discord.Member = None): await self._react(ctx, member, "odm")

    @commands.command(name="thunder_spear", aliases=["spear", "thunderspear"])
    async def thunder_spear(self, ctx, member: discord.Member = None): await self._react(ctx, member, "thunder_spear")

    @commands.command(name="nape", aliases=["napeslice"])
    async def nape(self, ctx, member: discord.Member = None): await self._react(ctx, member, "nape")

    @commands.command(name="titan_eat", aliases=["eaten", "titanbite"])
    async def titan_eat(self, ctx, member: discord.Member = None): await self._react(ctx, member, "titan_eat")

    @commands.command(name="rumble", aliases=["therumbling", "rumbling"])
    async def rumble(self, ctx, member: discord.Member = None): await self._react(ctx, member, "rumble")

    @commands.command(name="levi_kick", aliases=["levikick", "kick"])
    async def levi_kick(self, ctx, member: discord.Member = None): await self._react(ctx, member, "levi_kick")

    @commands.command(name="founding", aliases=["founding_titan", "foundingera"])
    async def founding(self, ctx, member: discord.Member = None): await self._react(ctx, member, "founding")

    @commands.command(name="scout", aliases=["scouts", "scoutregiment"])
    async def scout(self, ctx, member: discord.Member = None): await self._react(ctx, member, "scout")

    @commands.command(name="omni", aliases=["omnidir", "flash"])
    async def omni(self, ctx, member: discord.Member = None): await self._react(ctx, member, "omni")

    @commands.command(name="wall_break", aliases=["wallbreak", "breach"])
    async def wall_break(self, ctx, member: discord.Member = None): await self._react(ctx, member, "wall_break")

    @commands.command(name="colossal", aliases=["colossaltitan", "bertholdt"])
    async def colossal(self, ctx, member: discord.Member = None): await self._react(ctx, member, "colossal")

    @commands.command(name="war_hammer", aliases=["warhammer", "warhammertitan"])
    async def war_hammer(self, ctx, member: discord.Member = None): await self._react(ctx, member, "war_hammer")

    @commands.command(name="armored", aliases=["armoredtitan", "reiner"])
    async def armored(self, ctx, member: discord.Member = None): await self._react(ctx, member, "armored")

    @commands.command(name="freedom", aliases=["wingoffreedom", "fly"])
    async def freedom(self, ctx, member: discord.Member = None): await self._react(ctx, member, "freedom")

    # ── Help: list all commands ────────────────────────────────────────────
    @commands.command(name="reactions", aliases=["gifhelp", "gifcmds"])
    async def list_reactions(self, ctx):
        p = ctx.prefix.strip()
        social = ["hug", "pat", "slap", "bonk", "wave", "poke", "kiss", "cry", "blush", "bite", "cuddle", "dance", "laugh", "wink"]
        combat = ["punch", "transform", "salute", "scream", "charge", "slice", "yeager"]
        new_aot = ["kill", "odm", "thunder_spear", "nape", "titan_eat", "rumble", "levi_kick", "founding", "scout", "omni", "wall_break", "colossal", "war_hammer", "armored", "freedom"]

        embed = discord.Embed(
            title="🎭 AoT Reaction & Combat GIF Commands",
            description=f"Use `{p}<command> @user` for animated AoT GIFs!",
            color=discord.Color.dark_red(),
        )
        embed.add_field(
            name="💖 Social Reactions",
            value=" • ".join(f"`{p}{a}`" for a in social),
            inline=False
        )
        embed.add_field(
            name="⚔️ Original Combat",
            value=" • ".join(f"`{p}{a}`" for a in combat),
            inline=False
        )
        embed.add_field(
            name="💥 New AoT Special Commands",
            value=" • ".join(f"`{p}{a}`" for a in new_aot),
            inline=False
        )
        embed.add_field(
            name="💡 Aliases (examples)",
            value=(
                f"`{p}titan` = transform • `{p}tatakae` = yeager\n"
                f"`{p}spear` = thunder_spear • `{p}kick` = levi_kick\n"
                f"`{p}rumbling` = rumble • `{p}reiner` = armored\n"
                f"`{p}breach` = wall_break • `{p}fly` = freedom"
            ),
            inline=False
        )
        embed.set_footer(text="🪝 AoT Game Bot • Wings of Freedom")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Gifs(bot))
