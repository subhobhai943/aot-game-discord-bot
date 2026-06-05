"""OwO-style mini-games: coin flip, dice, slots, 8ball, rps, scramble, guess.
All commands use the server prefix (e.g. >flip, >dice, >slots, etc.)
"""
from __future__ import annotations
import asyncio
import random
import discord
from discord.ext import commands
from utils.game_state import GameState, SURVEY_CORPS_ICON

# ── AoT-themed slot symbols ──────────────────────────────────────────────
SLOT_SYMBOLS = ["👹", "⚔️", "🪺", "📜", "🛡️", "🐾", "🎯"]
SLOT_PAYOUTS = {
    "🎯": 500,  # Founding Titan jackpot
    "🐾": 200,  # Beast Titan triple
    "🪺": 100,  # ODM triple
    "⚔️": 75,   # Blade triple
    "👹": 50,   # Titan triple
    "📜": 30,   # Scroll triple
    "🛡️": 20,   # Shield triple
}

# ── 8-Ball responses ─────────────────────────────────────────────────
_8BALL_ANSWERS = [
    # Positive
    "✅ **It is certain.** Tatakae!",
    "✅ **Signs point to yes.** The Scouts believe in you!",
    "✅ **Without a doubt.** Dedicate your heart!",
    "✅ **Yes, definitely.** The Survey Corps approves!",
    "✅ **You may rely on it.** Historia confirms.",
    # Neutral
    "💭 **Reply hazy, try again.** Even Hange needs more data.",
    "💭 **Ask again later.** The Titans are restless.",
    "💭 **Better not tell you now.** Erwin keeps his secrets.",
    # Negative
    "❌ **Don’t count on it.** Reiner disagrees.",
    "❌ **My sources say no.** Zeke shakes his head.",
    "❌ **Very doubtful.** The Wall Titans aren’t moving for this.",
    "❌ **Outlook not so good.** The Rumbling approaches.",
]

# ── AoT-themed word scramble words ────────────────────────────────────
_WORDS = [
    ("EREN",    "The Attack Titan’s inheritor."),
    ("MIKASA",  "Strongest soldier of her generation."),
    ("TITANS",  "The enemies beyond the walls."),
    ("WALLS",   "Humanity’s last refuge."),
    ("LEVI",    "Humanity’s strongest soldier."),
    ("ARMIN",   "Inheritor of the Colossal Titan."),
    ("SCOUTS",  "The Survey Corps."),
    ("FREEDOM", "Eren’s ultimate goal."),
    ("PARADIS", "Island protected by walls."),
    ("ZEKE",    "The Beast Titan’s inheritor."),
    ("ANNIE",   "Female Titan inheritor."),
    ("RUMBLING","Eren’s final plan."),
    ("HISTORIA","Queen of the Walls."),
    ("HANGE",   "AoT’s most passionate scientist."),
    ("ERWIN",   "Commander of the Survey Corps."),
]


class OwoGames(commands.Cog):
    """OwO-style AoT mini-games."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._active_guesses: dict[int, tuple[str, str]] = {}  # channel_id -> (word, hint)
        self._active_scrambles: dict[int, tuple[str, str]] = {}  # channel_id -> (word, scrambled)

    # ── >flip ───────────────────────────────────────────────────────────
    @commands.command(name="flip", aliases=["coinflip", "cf"])
    async def flip(self, ctx: commands.Context, bet: str = None):
        """Flip a coin! Usage: >flip [heads/tails]"""
        result = random.choice(["heads", "tails"])
        emoji  = "🪙" if result == "heads" else "🔙"
        embed  = discord.Embed(
            title=f"{emoji} Coin Flip!",
            description=f"The coin landed on... **{result.upper()}**!",
            color=0xFFAA00
        )
        if bet and bet.lower() in ("heads", "tails"):
            if bet.lower() == result:
                embed.add_field(name="🎉 Result", value="You guessed correctly! *Tatakae!*", inline=False)
                embed.color = 0x55AA55
            else:
                embed.add_field(name="💥 Result", value="Wrong guess! *The Titans won this round.*", inline=False)
                embed.color = 0xFF3333
        embed.set_thumbnail(url=SURVEY_CORPS_ICON)
        await ctx.send(embed=embed)

    # ── >dice ───────────────────────────────────────────────────────────
    @commands.command(name="dice", aliases=["roll", "d6"])
    async def dice(self, ctx: commands.Context, sides: int = 6):
        """Roll a dice! Usage: >dice [sides=6]"""
        sides = max(2, min(sides, 100))
        result = random.randint(1, sides)
        embed = discord.Embed(
            title=f"🎲 Dice Roll (d{sides})",
            description=f"You rolled a **{result}**!",
            color=0x5599FF
        )
        if result == sides:
            embed.add_field(name="🎉 Max Roll!", value="Critical hit! *Levi is impressed.*", inline=False)
        elif result == 1:
            embed.add_field(name="💥 Min Roll!", value="Critical fail! *The titans are laughing.*", inline=False)
        embed.set_thumbnail(url=SURVEY_CORPS_ICON)
        await ctx.send(embed=embed)

    # ── >slots ──────────────────────────────────────────────────────────
    @commands.command(name="slots", aliases=["slot", "spin"])
    async def slots(self, ctx: commands.Context):
        """Play the AoT slot machine! Usage: >slots"""
        s1, s2, s3 = random.choices(SLOT_SYMBOLS, weights=[5,10,12,15,15,18,20], k=3)
        line = f"[ {s1} | {s2} | {s3} ]"

        if s1 == s2 == s3:
            payout = SLOT_PAYOUTS.get(s1, 10)
            player = GameState.get_player(str(ctx.author.id), ctx.author.display_name)
            player.coins += payout
            GameState.save_player(player)
            embed = discord.Embed(
                title="🎉 JACKPOT!",
                description=f"`{line}`\n\n**TRIPLE {s1}! You win {payout} coins!**",
                color=0xFFAA00
            )
            embed.add_field(name="💰 Coins Earned", value=f"+{payout}", inline=True)
        elif s1 == s2 or s2 == s3 or s1 == s3:
            payout = 10
            player = GameState.get_player(str(ctx.author.id), ctx.author.display_name)
            player.coins += payout
            GameState.save_player(player)
            embed = discord.Embed(
                title="✨ Partial Match!",
                description=f"`{line}`\n\nTwo matching symbols! You win {payout} coins.",
                color=0x55AA55
            )
            embed.add_field(name="💰 Coins Earned", value=f"+{payout}", inline=True)
        else:
            embed = discord.Embed(
                title="🖤 No Match",
                description=f"`{line}`\n\nNo matching symbols. The Titans mock you.",
                color=0x888888
            )
        embed.set_thumbnail(url=SURVEY_CORPS_ICON)
        await ctx.send(embed=embed)

    # ── >8ball ──────────────────────────────────────────────────────────
    @commands.command(name="8ball", aliases=["ask", "magic8"])
    async def eightball(self, ctx: commands.Context, *, question: str = ""):
        """Ask the AoT 8-ball a question! Usage: >8ball <question>"""
        if not question:
            await ctx.send("❌ Please ask a question! Example: `>8ball Will I catch a Founding Titan?`")
            return
        answer = random.choice(_8BALL_ANSWERS)
        embed = discord.Embed(
            title="🌀 AoT Magic 8-Ball",
            color=0xAA55FF
        )
        embed.add_field(name="❓ Question", value=question,  inline=False)
        embed.add_field(name="🔮 Answer",   value=answer,   inline=False)
        embed.set_thumbnail(url=SURVEY_CORPS_ICON)
        await ctx.send(embed=embed)

    # ── >rps ────────────────────────────────────────────────────────────
    @commands.command(name="rps", aliases=["rockpaperscissors"])
    async def rps(self, ctx: commands.Context, choice: str = ""):
        """Rock Paper Scissors AoT style! Usage: >rps <rock/paper/scissors>"""
        # AoT names
        aot_map = {
            "rock":     ("Rock",     "🧱", "Armored Titan"),
            "paper":    ("Paper",    "📜", "Founding Titan"),
            "scissors": ("Scissors", ✂️", "ODM Blades"),
        }
        bot_choices = ["rock", "paper", "scissors"]
        beats = {"rock": "scissors", "paper": "rock", "scissors": "paper"}

        if choice.lower() not in aot_map:
            await ctx.send("❌ Choose: `rock`, `paper`, or `scissors`! Example: `>rps rock`")
            return

        player_choice = choice.lower()
        bot_choice    = random.choice(bot_choices)

        p_name, p_emoji, p_aot = aot_map[player_choice]
        b_name, b_emoji, b_aot = aot_map[bot_choice]

        if player_choice == bot_choice:
            result, color = "It’s a tie! *Even the Titans are confused.*", 0xAAAA00
        elif beats[player_choice] == bot_choice:
            result, color = f"🎉 **You win!** *{p_aot} defeats {b_aot}!*", 0x55AA55
            p = GameState.get_player(str(ctx.author.id), ctx.author.display_name)
            p.coins += 5
            GameState.save_player(p)
        else:
            result, color = f"💥 **Bot wins!** *{b_aot} defeats {p_aot}!*", 0xFF3333

        embed = discord.Embed(
            title="⚔️ Rock Paper Scissors",
            description=(
                f"You: {p_emoji} **{p_name}** ({p_aot})\n"
                f"Bot: {b_emoji} **{b_name}** ({b_aot})\n\n"
                f"{result}"
            ),
            color=color
        )
        embed.set_thumbnail(url=SURVEY_CORPS_ICON)
        await ctx.send(embed=embed)

    # ── >scramble ────────────────────────────────────────────────────────
    @commands.command(name="scramble", aliases=["wordscramble", "unscramble"])
    async def scramble(self, ctx: commands.Context):
        """Unscramble an AoT word! Usage: >scramble"""
        if ctx.channel.id in self._active_scrambles:
            word, scrambled = self._active_scrambles[ctx.channel.id]
            await ctx.send(f"⚠️ A scramble is already active! Current scramble: `{scrambled}`")
            return

        word, hint = random.choice(_WORDS)
        letters = list(word)
        random.shuffle(letters)
        while "".join(letters) == word:
            random.shuffle(letters)
        scrambled = "".join(letters)
        self._active_scrambles[ctx.channel.id] = (word, scrambled)

        embed = discord.Embed(
            title="🔤 Word Scramble!",
            description=f"Unscramble this AoT word: **`{scrambled}`**\n\nHint: _{hint}_",
            color=0x5599FF
        )
        embed.set_footer(text="Type your answer in chat! You have 30 seconds.")
        embed.set_thumbnail(url=SURVEY_CORPS_ICON)
        await ctx.send(embed=embed)

        def check(m: discord.Message):
            return (
                m.channel == ctx.channel
                and not m.author.bot
                and m.content.upper().strip() == word
            )

        try:
            msg = await self.bot.wait_for("message", timeout=30.0, check=check)
            self._active_scrambles.pop(ctx.channel.id, None)
            p = GameState.get_player(str(msg.author.id), msg.author.display_name)
            p.coins += 15
            p.add_xp(10)
            GameState.save_player(p)
            await ctx.send(
                f"🎉 {msg.author.mention} got it! The word was **{word}**! *+15 coins, +10 XP*"
            )
        except asyncio.TimeoutError:
            self._active_scrambles.pop(ctx.channel.id, None)
            await ctx.send(f"⏰ Time’s up! The word was **{word}**.")

    # ── >guess ──────────────────────────────────────────────────────────
    @commands.command(name="guess", aliases=["numbguess", "numguess"])
    async def guess(self, ctx: commands.Context):
        """Guess a number between 1-100! Usage: >guess"""
        if ctx.channel.id in self._active_guesses:
            await ctx.send("⚠️ A guess game is already running in this channel!")
            return

        number = random.randint(1, 100)
        self._active_guesses[ctx.channel.id] = number
        attempts = 7
        guesses_left = attempts

        embed = discord.Embed(
            title="🤔 Number Guess",
            description=(
                f"I’ve chosen a number between **1 and 100**!\n"
                f"You have **{attempts} attempts**. Type your guess!"
            ),
            color=0xAA55FF
        )
        embed.set_thumbnail(url=SURVEY_CORPS_ICON)
        await ctx.send(embed=embed)

        def check(m: discord.Message):
            return m.channel == ctx.channel and not m.author.bot and m.content.isdigit()

        while guesses_left > 0:
            try:
                msg = await self.bot.wait_for("message", timeout=30.0, check=check)
            except asyncio.TimeoutError:
                self._active_guesses.pop(ctx.channel.id, None)
                await ctx.send(f"⏰ Time’s up! The number was **{number}**.")
                return

            guess_val = int(msg.content)
            guesses_left -= 1

            if guess_val == number:
                self._active_guesses.pop(ctx.channel.id, None)
                p = GameState.get_player(str(msg.author.id), msg.author.display_name)
                reward = guesses_left * 10 + 10
                p.coins += reward
                p.add_xp(20)
                GameState.save_player(p)
                await ctx.send(
                    f"🎉 {msg.author.mention} got it in **{attempts - guesses_left}** guess(es)! "
                    f"The number was **{number}**! *+{reward} coins, +20 XP*"
                )
                return
            elif guess_val < number:
                await ctx.send(f"⬆️ Too low! **{guesses_left}** guess(es) left.")
            else:
                await ctx.send(f"⬇️ Too high! **{guesses_left}** guess(es) left.")

        self._active_guesses.pop(ctx.channel.id, None)
        await ctx.send(f"💥 Out of guesses! The number was **{number}**.")

    # ── >games ──────────────────────────────────────────────────────────
    @commands.command(name="games", aliases=["gamelist", "minigames"])
    async def games_list(self, ctx: commands.Context):
        """Show all available mini-games."""
        prefix = ctx.prefix or ">"
        embed = discord.Embed(
            title="🎮 AoT Mini-Games",
            description="All OwO-style games, AoT-themed!",
            color=0xFFAA00
        )
        embed.add_field(
            name="🎲 Luck Games",
            value=(
                f"`{prefix}flip [heads/tails]` — Coin flip\n"
                f"`{prefix}dice [sides]` — Roll a dice\n"
                f"`{prefix}slots` — AoT slot machine\n"
                f"`{prefix}rps <rock/paper/scissors>` — Rock Paper Scissors"
            ),
            inline=False
        )
        embed.add_field(
            name="🧠 Skill Games",
            value=(
                f"`{prefix}scramble` — Unscramble an AoT word\n"
                f"`{prefix}guess` — Guess a number (1-100)"
            ),
            inline=False
        )
        embed.add_field(
            name="🔮 Other",
            value=f"`{prefix}8ball <question>` — Ask the AoT Magic 8-ball",
            inline=False
        )
        embed.add_field(
            name="👹 Titan Games",
            value=(
                f"`{prefix}catch` — Catch spawned titans\n"
                f"`{prefix}battle @user` — PvP titan battle\n"
                f"`{prefix}fight <char> vs <titan>` — PvE battle\n"
                f"`{prefix}collection` — View your titans"
            ),
            inline=False
        )
        embed.set_thumbnail(url=SURVEY_CORPS_ICON)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(OwoGames(bot))
