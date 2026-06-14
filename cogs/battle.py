"""PvE Battle Cog — Fully animated, button-driven, cinematic AoT battles.

Features:
  - Animated GIF per move (fetched live via utils/gifs.py)
  - Discord UI Buttons (no more typing commands)
  - Combo system (chain moves for bonus damage)
  - Critical hit system with dramatic flair
  - Status effects: BURN, STUN, SHIELD, RAGE
  - Cinematic HP bar with color urgency
  - Dynamic battle narration lines
  - Victory / defeat screens with rewards summary
  - Cooldown protection (one move per 3s)
"""
from __future__ import annotations
import asyncio
import random
import time
import discord
from discord.ext import commands
from discord import app_commands
from utils.game_state import (
    GameState, TITAN_STATS, calc_move, titan_ai_move,
    CHARACTERS, RARITY_COLOR, RARITY_EMOJI,
)
from utils.gifs import get_gif

# ── Move GIF keys (mapped to utils/gifs.py QUERY_MAP) ───────────────────
MOVE_GIF: dict[str, str] = {
    "slash":         "slice",
    "odm_dash":      "odm",
    "thunder_spear": "thunder_spear",
    "spiral_cut":    "nape",
    "titan_smash":   "charge",
    "defend":        "salute",
    "rage_mode":     "yeager",
}

# Titan attack GIF keys
TITAN_GIF: dict[str, str] = {
    "Pure Titan":       "titan_eat",
    "Abnormal Titan":   "titan_eat",
    "Cart Titan":       "armored",
    "Jaw Titan":        "slice",
    "Female Titan":     "charge",
    "Armored Titan":    "armored",
    "Attack Titan":     "yeager",
    "Beast Titan":      "wall_break",
    "War Hammer Titan": "war_hammer",
    "Colossal Titan":   "colossal",
    "Founding Titan":   "founding",
}

# ── Status effects ──────────────────────────────────────────────────────
STATUS = {
    "BURN":   {"emoji": "\U0001f525", "desc": "Burning! Loses 15 HP/round",       "color": 0xFF4500},
    "STUN":   {"emoji": "\u26a1",     "desc": "Stunned! Skips next attack",        "color": 0xFFFF00},
    "SHIELD": {"emoji": "\U0001f6e1\ufe0f", "desc": "Shielded! Next hit blocked", "color": 0x00BFFF},
    "RAGE":   {"emoji": "\U0001f7e5", "desc": "RAGE MODE! +30% damage",            "color": 0xFF0000},
}

# ── Move metadata ─────────────────────────────────────────────────────────────
MOVE_META = {
    "slash":         {"label": "\u2694\ufe0f Slash",        "style": discord.ButtonStyle.red,     "crit_chance": 0.15, "status_apply": None,     "dmg": (40, 70),  "miss": 0.10},
    "odm_dash":      {"label": "\U0001fab6 ODM Dash",      "style": discord.ButtonStyle.blurple, "crit_chance": 0.10, "status_apply": None,     "dmg": (25, 55),  "miss": 0.05},
    "thunder_spear": {"label": "\U0001f4a5 T-Spear",       "style": discord.ButtonStyle.red,     "crit_chance": 0.25, "status_apply": "BURN",   "dmg": (60, 100), "miss": 0.20},
    "spiral_cut":    {"label": "\U0001f300 Spiral Cut",    "style": discord.ButtonStyle.blurple, "crit_chance": 0.20, "status_apply": None,     "dmg": (35, 65),  "miss": 0.12},
    "titan_smash":   {"label": "\U0001f9f1 Titan Smash",   "style": discord.ButtonStyle.red,     "crit_chance": 0.12, "status_apply": "STUN",   "dmg": (55, 90),  "miss": 0.18},
    "defend":        {"label": "\U0001f6e1\ufe0f Defend",  "style": discord.ButtonStyle.green,   "crit_chance": 0.00, "status_apply": "SHIELD", "dmg": (0, 0),    "miss": 0.00},
    "rage_mode":     {"label": "\U0001f7e5 RAGE",          "style": discord.ButtonStyle.red,     "crit_chance": 0.30, "status_apply": "RAGE",   "dmg": (70, 120), "miss": 0.25},
}

# ── Cinematic narration banks ───────────────────────────────────────────────
HIT_LINES = [
    "The nape is exposed! \u26a1",
    "A clean cut through the hardened skin!",
    "Blades find their mark! \U0001f5e1\ufe0f",
    "The Survey Corps training pays off!",
    "ODM gear whirs as they close in fast!",
    "The titan staggers backward!",
    "\"Fight! Fight! FIGHT!\" \u2014 Eren echoes in their mind.",
    "The Wings of Freedom carry them forward! \U0001f985",
]
MISS_LINES = [
    "The titan's harden deflects the blade! \U0001f4a8",
    "Too slow \u2014 the titan swipes them away!",
    "The ODM wire snaps at the worst moment!",
    "A stumble on the rooftop \u2014 the hit misses!",
    "Crystal armor absorbs the blow!",
    "\"Not yet\u2026\" they whisper through gritted teeth.",
]
CRIT_LINES = [
    "\U0001f4a5 **CRITICAL HIT!** The nape explodes with steam!",
    "\U0001f525 **DEVASTATING BLOW!** The titan shrieks!",
    "\u26a1 **PERFECT STRIKE!** Just like Captain Levi!",
    "\U0001f31f **ULTRA COMBO!** The crowd goes wild!",
    "\U0001f3c6 **MONSTER DAMAGE!** Scouts everywhere salute!",
]
TITAN_HIT_LINES = [
    "The titan's massive fist connects! \U0001f9b4",
    "Walls crumble under the titan's power!",
    "\"Run!\" \u2014 but it's too late to dodge!",
    "The shockwave sends scouts flying!",
    "Hardened crystal slams into their path!",
]
DEFEAT_LINES = [
    "Even the strongest scouts fall sometimes. Rise again, cadet.",
    "\"The world is cruel\u2026\" \u2014 your battle ends here.",
    "The titan claims another victim today.",
    "Humanity retreats behind the walls once more.",
]
VICTORY_LINES = [
    "\"Tatakae! Tatakae! TATAKAE!\" The titan falls!",
    "The nape is severed \u2014 steam rises to the sky! \U0001f32b\ufe0f",
    "Another titan slain for humanity's freedom! \U0001f985",
    "The Survey Corps will sing of this battle!",
    "\"If you win, you live. If you lose, you die.\" \u2014 You WON.",
]

# ── HP bar ─────────────────────────────────────────────────────────────────────
def _hp_bar(current: int, maximum: int, length: int = 12) -> str:
    pct    = current / maximum if maximum > 0 else 0
    filled = max(0, int(pct * length))
    if pct > 0.6:
        bar_char = "\U0001f7e9"  # green
    elif pct > 0.3:
        bar_char = "\U0001f7e8"  # yellow
    else:
        bar_char = "\U0001f7e5"  # red
    empty = "\u2b1b"
    bar   = bar_char * filled + empty * (length - filled)
    return f"{bar} **{current}/{maximum}** `({int(pct * 100)}%)`"


# ── Live battle state ──────────────────────────────────────────────────────────────
class LiveBattle:
    """Extended battle state with combo, crits, and status effects."""
    __slots__ = (
        "user_id", "username", "scout_name", "titan_name",
        "scout_hp", "scout_max_hp", "titan_hp", "titan_max_hp",
        "round_num", "active",
        "combo", "scout_status", "titan_status",
        "last_move", "last_used", "xp_earned", "coins_earned",
        "channel_id", "message_id",
    )

    def __init__(self, user_id: str, username: str, scout_name: str, titan_name: str):
        t = TITAN_STATS.get(titan_name, {"hp": 300})
        scout_hp_map = {
            "Levi Ackerman": 320, "Mikasa Ackerman": 300, "Erwin Smith": 280,
            "Reiner Braun": 300, "Annie Leonhart": 290, "Eren Yeager": 280,
            "Bertholdt Hoover": 280, "Hange Zoe": 260, "Armin Arlert": 240,
        }
        self.user_id       = user_id
        self.username      = username
        self.scout_name    = scout_name
        self.titan_name    = titan_name
        self.scout_hp      = scout_hp_map.get(scout_name, 280)
        self.scout_max_hp  = self.scout_hp
        self.titan_hp      = t["hp"]
        self.titan_max_hp  = t["hp"]
        self.round_num     = 1
        self.active        = True
        self.combo         = 0
        self.scout_status: str | None = None
        self.titan_status: str | None = None
        self.last_move     = ""
        self.last_used     = 0.0
        self.xp_earned     = 0
        self.coins_earned  = 0
        self.channel_id    = 0
        self.message_id    = 0


_BATTLES: dict[str, LiveBattle] = {}


# ── Button View ──────────────────────────────────────────────────────────────────
class BattleView(discord.ui.View):
    def __init__(self, battle: LiveBattle, cog: "Battle"):
        super().__init__(timeout=120)
        self.battle = battle
        self.cog    = cog
        self._add_buttons()

    def _add_buttons(self):
        self.clear_items()
        for move_key in ["slash", "odm_dash", "thunder_spear"]:
            meta = MOVE_META[move_key]
            btn  = discord.ui.Button(
                label=meta["label"], style=meta["style"],
                custom_id=move_key, row=0
            )
            btn.callback = self._make_callback(move_key)
            self.add_item(btn)
        for move_key in ["spiral_cut", "titan_smash", "defend"]:
            meta = MOVE_META[move_key]
            btn  = discord.ui.Button(
                label=meta["label"], style=meta["style"],
                custom_id=move_key, row=1
            )
            btn.callback = self._make_callback(move_key)
            self.add_item(btn)
        rage_btn = discord.ui.Button(
            label=MOVE_META["rage_mode"]["label"],
            style=discord.ButtonStyle.red,
            custom_id="rage_mode", row=2,
            disabled=(self.battle.combo < 3)
        )
        rage_btn.callback = self._make_callback("rage_mode")
        self.add_item(rage_btn)
        flee_btn = discord.ui.Button(
            label="\U0001f3c3 Flee", style=discord.ButtonStyle.grey,
            custom_id="flee", row=2
        )
        flee_btn.callback = self._flee_callback
        self.add_item(flee_btn)

    def _make_callback(self, move_key: str):
        async def callback(interaction: discord.Interaction):
            if str(interaction.user.id) != self.battle.user_id:
                await interaction.response.send_message(
                    "\u274c This isn't your battle!", ephemeral=True
                )
                return
            now = time.time()
            if now - self.battle.last_used < 3.0:
                remaining = 3.0 - (now - self.battle.last_used)
                await interaction.response.send_message(
                    f"\u23f3 Cooldown! Wait **{remaining:.1f}s** before your next move.",
                    ephemeral=True
                )
                return
            self.battle.last_used = now
            await interaction.response.defer()
            await self.cog.process_move(interaction, self.battle, move_key)
        return callback

    async def _flee_callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.battle.user_id:
            await interaction.response.send_message("\u274c Not your battle!", ephemeral=True)
            return
        self.battle.active = False
        _BATTLES.pop(self.battle.user_id, None)
        self.stop()
        self.disable_all()
        username   = self.battle.username
        titan_name = self.battle.titan_name
        await interaction.response.edit_message(
            content=f"\U0001f3c3 **{username}** fled from **{titan_name}**! Coward or survivor? \U0001f914",
            embed=None, view=self
        )

    def disable_all(self):
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True


# ── Status bar helper ───────────────────────────────────────────────────────────
def _status_bar(battle: LiveBattle) -> str:
    parts = []
    if battle.scout_status:
        s = STATUS[battle.scout_status]
        parts.append(f"{s['emoji']} **Scout:** {battle.scout_status}")
    if battle.titan_status:
        s = STATUS[battle.titan_status]
        parts.append(f"{s['emoji']} **Titan:** {battle.titan_status}")
    if battle.combo >= 2:
        # FIX: pre-compute the lightning string outside the f-string
        # to avoid SyntaxError on Python < 3.12 (backslash in f-string expression)
        lightning = "\u26a1" * min(battle.combo, 5)
        parts.append(f"\U0001f525 **Combo x{battle.combo}** {lightning}")
    return "  \u2502  ".join(parts) if parts else "No active effects"


# ── Battle embed builder ────────────────────────────────────────────────────────
def _build_battle_embed(
    battle: LiveBattle,
    gif_url: str,
    round_log: list[str],
    title_override: str = "",
) -> discord.Embed:
    t_stats = TITAN_STATS.get(battle.titan_name, {})
    rarity  = t_stats.get("rarity", "Common")
    color   = RARITY_COLOR.get(rarity, 0x5599FF)
    if battle.scout_hp / battle.scout_max_hp < 0.25:
        color = 0xFF0000

    title = title_override or f"\u2694\ufe0f {battle.scout_name} vs {battle.titan_name} \u2014 Round {battle.round_num}"
    embed = discord.Embed(title=title, color=color)
    embed.add_field(
        name=f"\U0001f7e2 {battle.scout_name}",
        value=_hp_bar(battle.scout_hp, battle.scout_max_hp),
        inline=True
    )
    embed.add_field(
        name=f"\U0001f534 {battle.titan_name} {RARITY_EMOJI.get(rarity, '')}",
        value=_hp_bar(battle.titan_hp, battle.titan_max_hp),
        inline=True
    )
    embed.add_field(name="\u200b", value="\u200b", inline=True)
    embed.add_field(
        name="\u26a1 Effects & Combo",
        value=_status_bar(battle),
        inline=False
    )
    if round_log:
        embed.add_field(
            name=f"\U0001f4dc Round {battle.round_num} Log",
            value="\n".join(round_log),
            inline=False
        )
    if gif_url:
        embed.set_image(url=gif_url)
    combo_val  = battle.combo
    embed.set_footer(
        text=(
            f"\U0001f9e0 Combo: {combo_val}  |  "
            "\U0001f985 Wings of Freedom  |  "
            "Rage unlocks at Combo x3"
        )
    )
    return embed


# ── Main cog ───────────────────────────────────────────────────────────────────
class Battle(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /fight slash command ───────────────────────────────────────────────
    @app_commands.command(name="fight", description="Start an animated PvE battle against a titan!")
    @app_commands.describe(character="Your scout character", titan="Titan to fight")
    @app_commands.choices(
        character=[app_commands.Choice(name=c, value=c) for c in CHARACTERS],
        titan=[app_commands.Choice(name=t, value=t) for t in TITAN_STATS],
    )
    async def fight_slash(self, interaction: discord.Interaction, character: str, titan: str):
        uid = str(interaction.user.id)
        if uid in _BATTLES and _BATTLES[uid].active:
            await interaction.response.send_message(
                "\u274c You already have an active battle! Finish it first.", ephemeral=True
            )
            return
        await interaction.response.defer()
        await self._start_battle(
            interaction.followup.send, uid,
            interaction.user.display_name, character, titan
        )

    # ── >fight prefix command ──────────────────────────────────────────────
    @commands.command(name="fight", aliases=["pve", "startbattle"])
    async def fight_prefix(self, ctx: commands.Context, *, args: str = ""):
        """Start a PvE battle.  Usage: >fight <character> vs <titan>"""
        uid = str(ctx.author.id)
        if uid in _BATTLES and _BATTLES[uid].active:
            await ctx.send("\u274c You already have an active battle! Use `>flee` to quit it.")
            return
        if " vs " not in args:
            char_list  = ", ".join(CHARACTERS)
            titan_list = ", ".join(TITAN_STATS.keys())
            await ctx.send(
                f"\u274c **Usage:** `>fight <character> vs <titan>`\n"
                f"**Characters:** {char_list}\n"
                f"**Titans:** {titan_list}"
            )
            return
        # FIX: clean split — no bad tuple unpack
        split  = args.split(" vs ", 1)
        c_raw  = split[0].strip().title()
        t_raw  = split[1].strip().title()
        c_match = next((c for c in CHARACTERS  if c.lower() == c_raw.lower()), None)
        t_match = next((t for t in TITAN_STATS if t.lower() == t_raw.lower()), None)
        if not c_match:
            await ctx.send(f"\u274c Unknown character `{c_raw}`. Options: {', '.join(CHARACTERS)}")
            return
        if not t_match:
            await ctx.send(f"\u274c Unknown titan `{t_raw}`. Options: {', '.join(TITAN_STATS.keys())}")
            return
        await self._start_battle(ctx.send, uid, ctx.author.display_name, c_match, t_match)

    @commands.command(name="flee", aliases=["run", "escapebattle"])
    async def flee(self, ctx: commands.Context):
        """Flee from your active PvE battle."""
        uid = str(ctx.author.id)
        if uid not in _BATTLES:
            await ctx.send("\u274c No active battle to flee from!")
            return
        b = _BATTLES.pop(uid)
        await ctx.send(
            f"\U0001f3c3 **{ctx.author.display_name}** fled from **{b.titan_name}**! "
            "Coward or survivor? \U0001f914"
        )

    # ── Battle starter ─────────────────────────────────────────────────────────────
    async def _start_battle(
        self, send_fn, uid: str, username: str, character: str, titan: str
    ):
        battle  = LiveBattle(uid, username, character, titan)
        _BATTLES[uid] = battle

        gif_url = await get_gif("salute")
        t_stats = TITAN_STATS.get(titan, {})
        rarity  = t_stats.get("rarity", "Common")

        embed = discord.Embed(
            title=f"\U0001f9e8 BATTLE START \u2014 {character} vs {titan}!",
            description=(
                "> *\"If you win, you live. If you lose, you die. "
                "If you don't fight, you can't win!\"*\n"
                "> \u2014 Eren Yeager"
            ),
            color=RARITY_COLOR.get(rarity, 0x5599FF),
        )
        embed.add_field(
            name=f"\U0001f7e2 {character} (Scout)",
            value=_hp_bar(battle.scout_hp, battle.scout_max_hp),
            inline=True
        )
        embed.add_field(
            name=f"\U0001f534 {titan} {RARITY_EMOJI.get(rarity, '')} ({rarity})",
            value=_hp_bar(battle.titan_hp, battle.titan_max_hp),
            inline=True
        )
        if gif_url:
            embed.set_image(url=gif_url)
        embed.set_footer(text="\U0001f985 Wings of Freedom | Use the buttons below to fight!")

        view = BattleView(battle, self)
        await send_fn(embed=embed, view=view)

    # ── Core move processor ────────────────────────────────────────────────────
    async def process_move(
        self,
        interaction: discord.Interaction,
        battle: LiveBattle,
        move_key: str,
    ):
        if not battle.active:
            return

        meta    = MOVE_META.get(move_key, MOVE_META["slash"])
        gif_key = MOVE_GIF.get(move_key, "slice")
        log: list[str] = []
        gif_url = ""

        # ─ Stun check ─────────────────────────────────────────────────────────────
        if battle.scout_status == "STUN":
            battle.scout_status = None
            log.append(f"\u26a1 **{battle.scout_name}** recovers from stun \u2014 skipped this turn!")
        else:
            # ─ Defend ───────────────────────────────────────────────────────────────
            if move_key == "defend":
                battle.scout_status = "SHIELD"
                battle.combo = 0
                log.append(
                    f"\U0001f6e1\ufe0f **{battle.scout_name}** raises their blades in defence! "
                    "**SHIELD** active."
                )
                gif_url = await get_gif(gif_key)
            else:
                # ─ Attack ────────────────────────────────────────────────────────────
                missed = random.random() < meta["miss"]
                if missed:
                    battle.combo = 0
                    log.append(
                        f"\U0001f4a8 **{battle.scout_name}** {random.choice(MISS_LINES)}"
                    )
                else:
                    lo, hi = meta["dmg"]
                    dmg = random.randint(lo, hi)
                    if battle.scout_status == "RAGE":
                        dmg = int(dmg * 1.3)
                        log.append("\U0001f7e5 **RAGE ACTIVE!** +30% damage!")
                        battle.scout_status = None
                    battle.combo += 1
                    if battle.combo >= 2:
                        combo_bonus = battle.combo * 5
                        dmg += combo_bonus
                        log.append(
                            f"\U0001f525 **Combo x{battle.combo}!** +{combo_bonus} bonus damage!"
                        )
                    is_crit = random.random() < meta["crit_chance"]
                    if is_crit:
                        dmg = int(dmg * 1.75)
                        log.append(random.choice(CRIT_LINES))
                    else:
                        hit_line = random.choice(HIT_LINES)
                        log.append(
                            f"\u2705 **{battle.scout_name}** {hit_line} **\u2212{dmg} DMG**"
                        )
                    if meta["status_apply"] and random.random() < 0.35:
                        battle.titan_status = meta["status_apply"]
                        s = STATUS[meta["status_apply"]]
                        log.append(
                            f"{s['emoji']} Titan is now **{meta['status_apply']}**! {s['desc']}"
                        )
                    battle.titan_hp = max(0, battle.titan_hp - dmg)
                    gif_url = await get_gif(gif_key)

        # ─ Burn tick ────────────────────────────────────────────────────────────────
        if battle.titan_status == "BURN":
            battle.titan_hp = max(0, battle.titan_hp - 15)
            log.append("\U0001f525 Titan takes **15 burn damage!**")
            battle.titan_status = None

        # ─ Victory? ───────────────────────────────────────────────────────────────
        if battle.titan_hp <= 0:
            await self._handle_victory(interaction, battle, log)
            return

        # ─ Titan counter ───────────────────────────────────────────────────────────
        if battle.titan_status == "STUN":
            battle.titan_status = None
            log.append(f"\u26a1 **{battle.titan_name}** is stunned! Skipped its attack.")
        else:
            t_dmg, t_missed, t_desc = titan_ai_move()
            if battle.scout_status == "SHIELD":
                battle.scout_status = None
                log.append("\U0001f6e1\ufe0f **SHIELD BLOCKED** the titan's attack! No damage taken.")
                if not gif_url:
                    gif_url = await get_gif(TITAN_GIF.get(battle.titan_name, "titan_eat"))
            elif t_missed:
                log.append(f"\U0001f4a8 {battle.titan_name} {t_desc} \u2014 **MISSED!**")
            else:
                battle.scout_hp = max(0, battle.scout_hp - t_dmg)
                hit_line = random.choice(TITAN_HIT_LINES)
                log.append(
                    f"\U0001f534 {battle.titan_name} {hit_line} **\u2212{t_dmg} DMG**"
                )
                if not gif_url:
                    gif_url = await get_gif(TITAN_GIF.get(battle.titan_name, "titan_eat"))

        # ─ Defeat? ───────────────────────────────────────────────────────────────
        if battle.scout_hp <= 0:
            await self._handle_defeat(interaction, battle, log)
            return

        battle.round_num += 1
        view  = BattleView(battle, self)
        embed = _build_battle_embed(battle, gif_url, log)
        await interaction.edit_original_response(embed=embed, view=view)

    # ── Victory handler ───────────────────────────────────────────────────────────
    async def _handle_victory(
        self,
        interaction: discord.Interaction,
        battle: LiveBattle,
        log: list[str],
    ):
        battle.active = False
        _BATTLES.pop(battle.user_id, None)

        player  = await GameState.get_player(battle.user_id, battle.username)
        t_stats = TITAN_STATS.get(battle.titan_name, {"hp": 200, "rarity": "Common"})
        xp_gain = t_stats.get("hp", 200) // 4 + battle.combo * 5
        coins   = 25 + (10 if t_stats.get("rarity") in ("Epic", "Legendary") else 0)
        levelled = player.add_xp(xp_gain)
        player.coins += coins
        player.kills += 1
        player.wins  += 1
        await GameState.save_player(player)

        gif_url = await get_gif("freedom")
        embed   = discord.Embed(
            title=f"\U0001f3c6 VICTORY! {battle.scout_name} slays {battle.titan_name}!",
            description=random.choice(VICTORY_LINES),
            color=0x55AA55,
        )
        for line in log[-3:]:
            embed.description += f"\n{line}"  # type: ignore[operator]
        embed.add_field(name="\u26a1 XP Earned",        value=f"**+{xp_gain}** XP",      inline=True)
        embed.add_field(name="\U0001f4b0 Coins",         value=f"**+{coins}** coins",     inline=True)
        embed.add_field(name="\U0001f525 Max Combo",     value=f"**x{battle.combo}**",    inline=True)
        embed.add_field(name="\U0001f5e1\ufe0f Rounds",  value=f"**{battle.round_num}** rounds", inline=True)
        if levelled:
            embed.add_field(
                name="\U0001f31f LEVEL UP!",
                value=f"Now **Level {player.level}** \u2014 {player.rank}! \U0001f389",
                inline=False,
            )
        if gif_url:
            embed.set_image(url=gif_url)
        embed.set_footer(text="\U0001f985 Wings of Freedom | Use /fight to battle again!")

        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="\U0001f504 Battle Again",
            style=discord.ButtonStyle.green,
            custom_id="battle_again",
            disabled=True,
        ))
        await interaction.edit_original_response(embed=embed, view=view)

    # ── Defeat handler ───────────────────────────────────────────────────────────
    async def _handle_defeat(
        self,
        interaction: discord.Interaction,
        battle: LiveBattle,
        log: list[str],
    ):
        battle.active = False
        _BATTLES.pop(battle.user_id, None)

        player = await GameState.get_player(battle.user_id, battle.username)
        player.losses += 1
        player.add_xp(20)
        await GameState.save_player(player)

        gif_url = await get_gif("titan_eat")
        embed   = discord.Embed(
            title=f"\U0001f480 DEFEATED \u2014 {battle.titan_name} wins!",
            description=random.choice(DEFEAT_LINES),
            color=0xFF3333,
        )
        for line in log[-3:]:
            embed.description += f"\n{line}"  # type: ignore[operator]
        embed.add_field(name="\u26a1 Consolation XP",  value="**+20 XP**",              inline=True)
        embed.add_field(name="\U0001f4ca Losses",       value=f"**{player.losses}**",    inline=True)
        embed.add_field(name="\U0001f5e1\ufe0f Rounds", value=f"**{battle.round_num}**", inline=True)
        if gif_url:
            embed.set_image(url=gif_url)
        embed.set_footer(text="Survive and fight again. The Titans won't wait.")
        await interaction.edit_original_response(embed=embed, view=discord.ui.View())


async def setup(bot: commands.Bot):
    await bot.add_cog(Battle(bot))
