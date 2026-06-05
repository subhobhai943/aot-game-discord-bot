"""OwO-style mini-games: coin flip, dice, slots, 8ball, rps, scramble, guess.
All commands use the server prefix (e.g. Aot flip, Aot dice, Aot slots, etc.)
"""
from __future__ import annotations
import asyncio
import random
import discord
from discord.ext import commands
from utils.game_state import GameState, SURVEY_CORPS_ICON

SLOT_SYMBOLS = ["\U0001f479", "\u2694\ufe0f", "\U0001fa7a", "\U0001f4dc", "\U0001f6e1\ufe0f", "\U0001f43e", "\U0001f3af"]
SLOT_PAYOUTS = {
    "\U0001f3af": 500,
    "\U0001f43e": 200,
    "\U0001fa7a": 100,
    "\u2694\ufe0f": 75,
    "\U0001f479": 50,
    "\U0001f4dc": 30,
    "\U0001f6e1\ufe0f": 20,
}

_8BALL_ANSWERS = [
    "\u2705 **It is certain.** Tatakae!",
    "\u2705 **Signs point to yes.** The Scouts believe in you!",
    "\u2705 **Without a doubt.** Dedicate your heart!",
    "\u2705 **Yes, definitely.** The Survey Corps approves!",
    "\u2705 **You may rely on it.** Historia confirms.",
    "\U0001f4ad **Reply hazy, try again.** Even Hange needs more data.",
    "\U0001f4ad **Ask again later.** The Titans are restless.",
    "\U0001f4ad **Better not tell you now.** Erwin keeps his secrets.",
    "\u274c **Don\u2019t count on it.** Reiner disagrees.",
    "\u274c **My sources say no.** Zeke shakes his head.",
    "\u274c **Very doubtful.** The Wall Titans aren\u2019t moving for this.",
    "\u274c **Outlook not so good.** The Rumbling approaches.",
]

_WORDS = [
    ("EREN",     "The Attack Titan\u2019s inheritor."),
    ("MIKASA",   "Strongest soldier of her generation."),
    ("TITANS",   "The enemies beyond the walls."),
    ("WALLS",    "Humanity\u2019s last refuge."),
    ("LEVI",     "Humanity\u2019s strongest soldier."),
    ("ARMIN",    "Inheritor of the Colossal Titan."),
    ("SCOUTS",   "The Survey Corps."),
    ("FREEDOM",  "Eren\u2019s ultimate goal."),
    ("PARADIS",  "Island protected by walls."),
    ("ZEKE",     "The Beast Titan\u2019s inheritor."),
    ("ANNIE",    "Female Titan inheritor."),
    ("RUMBLING", "Eren\u2019s final plan."),
    ("HISTORIA", "Queen of the Walls."),
    ("HANGE",    "AoT\u2019s most passionate scientist."),
    ("ERWIN",    "Commander of the Survey Corps."),
]

RPS_MAP = {
    "rock":     ("Rock",     "\U0001f9f1", "Armored Titan"),
    "paper":    ("Paper",    "\U0001f4dc", "Founding Titan"),
    "scissors": ("Scissors", "\u2702",    "ODM Blades"),
}
RPS_BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}


class OwoGames(commands.Cog):
    """OwO-style AoT mini-games."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._active_scrambles: dict[int, tuple[str, str]] = {}
        self._active_guesses:   dict[int, int]             = {}

    @commands.command(name="flip", aliases=["coinflip", "cf"])
    async def flip(self, ctx: commands.Context, bet: str = None):
        """Flip a coin! Usage: Aot flip [heads/tails]"""
        result = random.choice(["heads", "tails"])
        emoji  = "\U0001fa99" if result == "heads" else "\U0001f519"
        embed  = discord.Embed(
            title=f"{emoji} Coin Flip!",
            description=f"The coin landed on... **{result.upper()}**!",
            color=0xFFAA00
        )
        if bet and bet.lower() in ("heads", "tails"):
            if bet.lower() == result:
                embed.add_field(name="\U0001f389 Result", value="You guessed right! *Tatakae!*", inline=False)
                embed.color = 0x55AA55
            else:
                embed.add_field(name="\U0001f4a5 Result", value="Wrong! *The Titans won this round.*", inline=False)
                embed.color = 0xFF3333
        embed.set_thumbnail(url=SURVEY_CORPS_ICON)
        await ctx.send(embed=embed)

    @commands.command(name="dice", aliases=["roll", "d6"])
    async def dice(self, ctx: commands.Context, sides: int = 6):
        """Roll a dice! Usage: Aot dice [sides]"""
        sides  = max(2, min(sides, 100))
        result = random.randint(1, sides)
        embed  = discord.Embed(
            title=f"\U0001f3b2 Dice Roll (d{sides})",
            description=f"You rolled a **{result}**!",
            color=0x5599FF
        )
        if result == sides:
            embed.add_field(name="\U0001f389 Max Roll!", value="Critical hit! *Levi is impressed.*", inline=False)
        elif result == 1:
            embed.add_field(name="\U0001f4a5 Min Roll!", value="Critical fail! *The titans are laughing.*", inline=False)
        embed.set_thumbnail(url=SURVEY_CORPS_ICON)
        await ctx.send(embed=embed)

    @commands.command(name="slots", aliases=["slot", "spin"])
    async def slots(self, ctx: commands.Context):
        """Play the AoT slot machine! Usage: Aot slots"""
        s1, s2, s3 = random.choices(SLOT_SYMBOLS, weights=[5, 10, 12, 15, 15, 18, 20], k=3)
        line = f"[ {s1} | {s2} | {s3} ]"
        if s1 == s2 == s3:
            payout = SLOT_PAYOUTS.get(s1, 10)
            p = GameState.get_player(str(ctx.author.id), ctx.author.display_name)
            p.coins += payout
            GameState.save_player(p)
            embed = discord.Embed(
                title="\U0001f389 JACKPOT!",
                description=f"`{line}`\n\n**TRIPLE {s1}! +{payout} coins!**",
                color=0xFFAA00
            )
            embed.add_field(name="\U0001f4b0 Coins", value=f"+{payout}", inline=True)
        elif s1 == s2 or s2 == s3 or s1 == s3:
            p = GameState.get_player(str(ctx.author.id), ctx.author.display_name)
            p.coins += 10
            GameState.save_player(p)
            embed = discord.Embed(
                title="\u2728 Partial Match!",
                description=f"`{line}`\n\nTwo matching! +10 coins.",
                color=0x55AA55
            )
        else:
            embed = discord.Embed(
                title="\U0001f5a4 No Match",
                description=f"`{line}`\n\nNo luck. The Titans mock you.",
                color=0x888888
            )
        embed.set_thumbnail(url=SURVEY_CORPS_ICON)
        await ctx.send(embed=embed)

    @commands.command(name="8ball", aliases=["ask", "magic8"])
    async def eightball(self, ctx: commands.Context, *, question: str = ""):
        """Ask the AoT 8-ball! Usage: Aot 8ball <question>"""
        if not question:
            await ctx.send("\u274c Provide a question! E.g. `Aot 8ball Will I catch a Founding Titan?`")
            return
        embed = discord.Embed(title="\U0001f300 AoT Magic 8-Ball", color=0xAA55FF)
        embed.add_field(name="\u2753 Question", value=question,                        inline=False)
        embed.add_field(name="\U0001f52e Answer",   value=random.choice(_8BALL_ANSWERS), inline=False)
        embed.set_thumbnail(url=SURVEY_CORPS_ICON)
        await ctx.send(embed=embed)

    @commands.command(name="rps", aliases=["rockpaperscissors"])
    async def rps(self, ctx: commands.Context, choice: str = ""):
        """Rock Paper Scissors AoT style! Usage: Aot rps <rock/paper/scissors>"""
        if choice.lower() not in RPS_MAP:
            await ctx.send("\u274c Choose: `rock`, `paper`, or `scissors`!")
            return
        player_choice = choice.lower()
        bot_choice    = random.choice(list(RPS_MAP.keys()))
        p_name, p_emoji, p_aot = RPS_MAP[player_choice]
        b_name, b_emoji, b_aot = RPS_MAP[bot_choice]
        if player_choice == bot_choice:
            result, color = "It\u2019s a tie! *Even the Titans are confused.*", 0xAAAA00
        elif RPS_BEATS[player_choice] == bot_choice:
            p = GameState.get_player(str(ctx.author.id), ctx.author.display_name)
            p.coins += 5; GameState.save_player(p)
            result, color = f"\U0001f389 **You win!** *{p_aot} defeats {b_aot}!* (+5 coins)", 0x55AA55
        else:
            result, color = f"\U0001f4a5 **Bot wins!** *{b_aot} defeats {p_aot}!*", 0xFF3333
        embed = discord.Embed(
            title="\u2694\ufe0f Rock Paper Scissors",
            description=(
                f"You: {p_emoji} **{p_name}** ({p_aot})\n"
                f"Bot: {b_emoji} **{b_name}** ({b_aot})\n\n{result}"
            ),
            color=color
        )
        embed.set_thumbnail(url=SURVEY_CORPS_ICON)
        await ctx.send(embed=embed)

    @commands.command(name="scramble", aliases=["wordscramble", "unscramble"])
    async def scramble(self, ctx: commands.Context):
        """Unscramble an AoT word! Usage: Aot scramble"""
        if ctx.channel.id in self._active_scrambles:
            _, scrambled = self._active_scrambles[ctx.channel.id]
            await ctx.send(f"\u26a0\ufe0f Scramble active! Current: `{scrambled}`")
            return
        word, hint = random.choice(_WORDS)
        letters = list(word)
        random.shuffle(letters)
        while "".join(letters) == word:
            random.shuffle(letters)
        scrambled = "".join(letters)
        self._active_scrambles[ctx.channel.id] = (word, scrambled)
        embed = discord.Embed(
            title="\U0001f524 Word Scramble!",
            description=f"Unscramble: **`{scrambled}`**\nHint: _{hint}_",
            color=0x5599FF
        )
        embed.set_footer(text="Type your answer in chat! 30 seconds.")
        embed.set_thumbnail(url=SURVEY_CORPS_ICON)
        await ctx.send(embed=embed)

        def check(m: discord.Message):
            return m.channel == ctx.channel and not m.author.bot and m.content.upper().strip() == word

        try:
            msg = await self.bot.wait_for("message", timeout=30.0, check=check)
            self._active_scrambles.pop(ctx.channel.id, None)
            p = GameState.get_player(str(msg.author.id), msg.author.display_name)
            p.coins += 15; p.add_xp(10); GameState.save_player(p)
            await ctx.send(f"\U0001f389 {msg.author.mention} got it! Word: **{word}** | +15 coins +10 XP")
        except asyncio.TimeoutError:
            self._active_scrambles.pop(ctx.channel.id, None)
            await ctx.send(f"\u23f0 Time\u2019s up! The word was **{word}**.")

    @commands.command(name="guess", aliases=["numguess", "numbguess"])
    async def guess(self, ctx: commands.Context):
        """Guess a number 1-100! Usage: Aot guess"""
        if ctx.channel.id in self._active_guesses:
            await ctx.send("\u26a0\ufe0f A guess game is already running here!")
            return
        number = random.randint(1, 100)
        self._active_guesses[ctx.channel.id] = number
        attempts = 7
        embed = discord.Embed(
            title="\U0001f914 Number Guess",
            description=f"I picked a number between **1 and 100**! You have **{attempts}** attempts.",
            color=0xAA55FF
        )
        embed.set_thumbnail(url=SURVEY_CORPS_ICON)
        await ctx.send(embed=embed)

        def check(m: discord.Message):
            return m.channel == ctx.channel and not m.author.bot and m.content.isdigit()

        left = attempts
        while left > 0:
            try:
                msg = await self.bot.wait_for("message", timeout=30.0, check=check)
            except asyncio.TimeoutError:
                self._active_guesses.pop(ctx.channel.id, None)
                await ctx.send(f"\u23f0 Time\u2019s up! The number was **{number}**.")
                return
            val = int(msg.content)
            left -= 1
            if val == number:
                self._active_guesses.pop(ctx.channel.id, None)
                p      = GameState.get_player(str(msg.author.id), msg.author.display_name)
                reward = left * 10 + 10
                p.coins += reward; p.add_xp(20); GameState.save_player(p)
                await ctx.send(
                    f"\U0001f389 {msg.author.mention} got **{number}** in "
                    f"**{attempts - left}** guess(es)! +{reward} coins +20 XP"
                )
                return
            elif val < number:
                await ctx.send(f"\u2b06\ufe0f Too low! {left} guess(es) left.")
            else:
                await ctx.send(f"\u2b07\ufe0f Too high! {left} guess(es) left.")

        self._active_guesses.pop(ctx.channel.id, None)
        await ctx.send(f"\U0001f4a5 Out of guesses! The number was **{number}**.")

    @commands.command(name="games", aliases=["gamelist", "minigames"])
    async def games_list(self, ctx: commands.Context):
        """Show all mini-games. Usage: Aot games"""
        p = ctx.prefix or "Aot "
        embed = discord.Embed(
            title="\U0001f3ae AoT Mini-Games",
            description="All OwO-style mini-games, AoT-themed!",
            color=0xFFAA00
        )
        embed.add_field(
            name="\U0001f3b2 Luck Games",
            value=(
                f"`{p}flip [heads/tails]` \u2014 Coin flip\n"
                f"`{p}dice [sides]` \u2014 Roll a dice\n"
                f"`{p}slots` \u2014 AoT slot machine\n"
                f"`{p}rps <rock/paper/scissors>` \u2014 RPS"
            ),
            inline=False
        )
        embed.add_field(
            name="\U0001f9e0 Skill Games",
            value=(
                f"`{p}scramble` \u2014 Unscramble an AoT word\n"
                f"`{p}guess` \u2014 Guess a number (1-100)"
            ),
            inline=False
        )
        embed.add_field(
            name="\U0001f52e Other",
            value=f"`{p}8ball <question>` \u2014 AoT Magic 8-ball",
            inline=False
        )
        embed.add_field(
            name="\U0001f479 Titan Games",
            value=(
                f"`{p}catch` \u2014 Catch spawned titans\n"
                f"`{p}battle @user` \u2014 PvP titan battle\n"
                f"`{p}fight <char> vs <titan>` \u2014 PvE battle\n"
                f"`{p}collection` \u2014 View your titans"
            ),
            inline=False
        )
        embed.set_thumbnail(url=SURVEY_CORPS_ICON)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(OwoGames(bot))
