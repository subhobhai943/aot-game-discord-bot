"""In-memory game state manager with JSON persistence.

FIX: TITAN_IMAGES now uses stable external image URLs (wiki/fandom CDN)
     instead of local assets in the repo. This keeps the bot lightweight
     and unlocks unlimited image variety — just swap the URL.
"""
from __future__ import annotations
import json
import os
import random
from dataclasses import dataclass, field, asdict
from typing import Optional

DATA_FILE        = "data/player_data.json"
SETTINGS_FILE    = "data/settings.json"

RANKS      = ["Cadet", "Scout", "Elite", "Captain", "Legend"]
XP_PER_LEVEL = 120

CHARACTERS = [
    "Eren Yeager", "Mikasa Ackerman", "Levi Ackerman",
    "Armin Arlert",  "Hange Zoe",      "Erwin Smith",
    "Reiner Braun",  "Annie Leonhart",  "Bertholdt Hoover",
]

TITANS = [
    "Armored Titan",   "Colossal Titan",   "Female Titan",
    "Beast Titan",     "War Hammer Titan", "Cart Titan",
    "Jaw Titan",       "Attack Titan",     "Founding Titan",
    "Pure Titan",      "Abnormal Titan",
]

# ── Titan stats for battles ────────────────────────────────────────────────
TITAN_STATS = {
    "Founding Titan":   {"hp": 500, "atk": 90, "def": 80, "spd": 60, "rarity": "Legendary"},
    "Colossal Titan":   {"hp": 450, "atk": 85, "def": 75, "spd": 40, "rarity": "Legendary"},
    "War Hammer Titan": {"hp": 400, "atk": 88, "def": 70, "spd": 65, "rarity": "Epic"},
    "Beast Titan":      {"hp": 380, "atk": 82, "def": 65, "spd": 70, "rarity": "Epic"},
    "Armored Titan":    {"hp": 360, "atk": 75, "def": 95, "spd": 55, "rarity": "Rare"},
    "Attack Titan":     {"hp": 320, "atk": 80, "def": 60, "spd": 80, "rarity": "Rare"},
    "Female Titan":     {"hp": 300, "atk": 78, "def": 72, "spd": 75, "rarity": "Rare"},
    "Jaw Titan":        {"hp": 260, "atk": 85, "def": 50, "spd": 95, "rarity": "Uncommon"},
    "Cart Titan":       {"hp": 240, "atk": 60, "def": 68, "spd": 85, "rarity": "Uncommon"},
    "Abnormal Titan":   {"hp": 180, "atk": 55, "def": 45, "spd": 90, "rarity": "Common"},
    "Pure Titan":       {"hp": 150, "atk": 45, "def": 40, "spd": 50, "rarity": "Common"},
}

TITAN_WEIGHTS = {
    "Pure Titan": 40, "Abnormal Titan": 30, "Cart Titan": 12,
    "Jaw Titan": 10, "Female Titan": 8, "Armored Titan": 6,
    "Attack Titan": 5, "Beast Titan": 4, "War Hammer Titan": 2,
    "Colossal Titan": 2, "Founding Titan": 1,
}

RARITY_COLOR = {
    "Common":    0xAAAAAA,
    "Uncommon":  0x55AA55,
    "Rare":      0x5599FF,
    "Epic":      0xAA55FF,
    "Legendary": 0xFFAA00,
}

RARITY_EMOJI = {
    "Common": "⬜", "Uncommon": "🟢", "Rare": "🔵", "Epic": "🟣", "Legendary": "🟡"
}

# ── Titan Images — external CDN URLs (no local assets needed) ─────────────
# Using Attack on Titan Wiki / Fandom CDN images.
# To add more images: just replace any URL here — no files to upload to the repo.
TITAN_IMAGES = {
    "Pure Titan":       "https://static.wikia.nocookie.net/shingekinokyojin/images/9/93/Pure_Titans_%28Anime%29.png",
    "Abnormal Titan":   "https://static.wikia.nocookie.net/shingekinokyojin/images/5/52/Abnormal_Titan_%28Anime%29.png",
    "Jaw Titan":        "https://static.wikia.nocookie.net/shingekinokyojin/images/3/35/Jaw_Titan_%28Anime%29.png",
    "Cart Titan":       "https://static.wikia.nocookie.net/shingekinokyojin/images/b/b3/Cart_Titan_%28Anime%29.png",
    "Female Titan":     "https://static.wikia.nocookie.net/shingekinokyojin/images/5/5b/Female_Titan_%28Anime%29.png",
    "Armored Titan":    "https://static.wikia.nocookie.net/shingekinokyojin/images/a/a8/Armored_Titan_%28Anime%29.png",
    "Attack Titan":     "https://static.wikia.nocookie.net/shingekinokyojin/images/7/73/Attack_Titan_%28Anime%29.png",
    "Colossal Titan":   "https://static.wikia.nocookie.net/shingekinokyojin/images/e/e4/Colossus_Titan_%28Anime%29.png",
    "Beast Titan":      "https://static.wikia.nocookie.net/shingekinokyojin/images/c/c8/Beast_Titan_%28Anime%29.png",
    "War Hammer Titan": "https://static.wikia.nocookie.net/shingekinokyojin/images/0/07/War_Hammer_Titan_%28Anime%29.png",
    "Founding Titan":   "https://static.wikia.nocookie.net/shingekinokyojin/images/7/79/Founding_Titan_%28Anime%29.png",
}
SURVEY_CORPS_ICON = "https://static.wikia.nocookie.net/shingekinokyojin/images/1/1e/Scout_Regiment_symbol.png"


@dataclass
class PlayerData:
    user_id:    str
    username:   str
    scout_name: str = "Eren Yeager"
    level:      int = 1
    xp:         int = 0
    wins:       int = 0
    losses:     int = 0
    kills:      int = 0
    coins:      int = 0
    # collection: {titan_name: count}
    collection: dict = field(default_factory=dict)
    # active titan for battles
    active_titan: str = ""

    @property
    def xp_needed(self) -> int:
        return self.level * XP_PER_LEVEL

    @property
    def rank(self) -> str:
        return RANKS[min(self.level // 5, len(RANKS) - 1)]

    def add_xp(self, amount: int) -> bool:
        self.xp += amount
        levelled = False
        while self.xp >= self.xp_needed:
            self.xp -= self.xp_needed
            self.level += 1
            levelled = True
        return levelled

    def add_titan(self, titan: str):
        self.collection[titan] = self.collection.get(titan, 0) + 1

    def total_titans(self) -> int:
        return sum(self.collection.values())

    def best_titan(self) -> Optional[str]:
        """Return the titan with the highest rarity in the collection."""
        order = ["Legendary", "Epic", "Rare", "Uncommon", "Common"]
        for rarity in order:
            for name, stats in TITAN_STATS.items():
                if stats["rarity"] == rarity and self.collection.get(name, 0) > 0:
                    return name
        return None


@dataclass
class BattleSession:
    player_id:    str
    scout_name:   str
    titan_name:   str
    scout_hp:     int
    scout_max_hp: int
    titan_hp:     int
    titan_max_hp: int
    round_num:    int = 1
    active:       bool = True
    last_action:  str = ""
    channel_id:   Optional[int] = None


@dataclass
class PvPSession:
    challenger_id:    str
    opponent_id:      str
    challenger_titan: str
    opponent_titan:   str
    challenger_hp:    int
    opponent_hp:      int
    challenger_max:   int
    opponent_max:     int
    current_turn:     str  = ""   # user_id whose turn it is
    round_num:        int  = 1
    active:           bool = True
    message_id:       int  = 0
    channel_id:       int  = 0


class GameState:
    _players:  dict[str, PlayerData]    = {}
    _battles:  dict[str, BattleSession] = {}
    _pvp:      dict[str, PvPSession]    = {}   # key = challenger_id
    _settings: dict = {}

    # ── persistence ───────────────────────────────────────────────────────
    @classmethod
    def _ensure_dir(cls):
        os.makedirs("data", exist_ok=True)

    @classmethod
    def _load(cls):
        cls._ensure_dir()
        if not os.path.exists(DATA_FILE):
            return
        try:
            with open(DATA_FILE, encoding="utf-8") as f:
                raw = json.load(f)
            for uid, d in raw.items():
                d.setdefault("kills", 0)
                d.setdefault("coins", 0)
                d.setdefault("collection", {})
                d.setdefault("active_titan", "")
                cls._players[uid] = PlayerData(**d)
        except Exception as e:
            print(f"[GameState] Could not load player data: {e}")

    @classmethod
    def _save(cls):
        cls._ensure_dir()
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {uid: asdict(p) for uid, p in cls._players.items()},
                    f, indent=2
                )
        except Exception as e:
            print(f"[GameState] Could not save player data: {e}")

    @classmethod
    def load_settings(cls):
        cls._ensure_dir()
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, encoding="utf-8") as f:
                    cls._settings = json.load(f)
            except Exception:
                cls._settings = {}

    @classmethod
    def save_settings(cls):
        cls._ensure_dir()
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(cls._settings, f, indent=2)

    @classmethod
    def get_spawn_channel(cls, guild_id: int) -> Optional[int]:
        cls.load_settings()
        return cls._settings.get(str(guild_id), {}).get("spawn_channel")

    @classmethod
    def set_spawn_channel(cls, guild_id: int, channel_id: int):
        cls.load_settings()
        cls._settings.setdefault(str(guild_id), {})["spawn_channel"] = channel_id
        cls.save_settings()

    # ── player management ─────────────────────────────────────────────────
    @classmethod
    def get_player(cls, user_id: str, username: str) -> PlayerData:
        if not cls._players:
            cls._load()
        if user_id not in cls._players:
            cls._players[user_id] = PlayerData(user_id=user_id, username=username)
            cls._save()
        return cls._players[user_id]

    @classmethod
    def save_player(cls, player: PlayerData):
        cls._players[player.user_id] = player
        cls._save()

    @classmethod
    def all_players(cls) -> list[PlayerData]:
        if not cls._players:
            cls._load()
        return list(cls._players.values())

    # ── PvE battles ───────────────────────────────────────────────────────
    @classmethod
    def start_battle(cls, player_id, scout_name, titan_name, channel_id) -> BattleSession:
        t = TITAN_STATS.get(titan_name, {"hp": 300, "atk": 60, "def": 50, "spd": 50})
        scout_hp_map = {
            "Levi Ackerman": 320, "Mikasa Ackerman": 300, "Erwin Smith": 280,
            "Reiner Braun": 300, "Annie Leonhart": 290, "Eren Yeager": 280,
            "Bertholdt Hoover": 280, "Hange Zoe": 260, "Armin Arlert": 240,
        }
        s_hp = scout_hp_map.get(scout_name, 280)
        session = BattleSession(
            player_id=player_id, scout_name=scout_name, titan_name=titan_name,
            scout_hp=s_hp, scout_max_hp=s_hp, titan_hp=t["hp"], titan_max_hp=t["hp"],
            channel_id=channel_id,
        )
        cls._battles[player_id] = session
        return session

    @classmethod
    def get_battle(cls, player_id: str) -> Optional[BattleSession]:
        return cls._battles.get(player_id)

    @classmethod
    def end_battle(cls, player_id: str):
        cls._battles.pop(player_id, None)

    # ── PvP management ────────────────────────────────────────────────────
    @classmethod
    def start_pvp(cls, challenger_id, opponent_id, c_titan, o_titan) -> PvPSession:
        cs  = TITAN_STATS.get(c_titan,  {"hp": 300})
        os_ = TITAN_STATS.get(o_titan,  {"hp": 300})
        session = PvPSession(
            challenger_id=challenger_id, opponent_id=opponent_id,
            challenger_titan=c_titan, opponent_titan=o_titan,
            challenger_hp=cs["hp"],  opponent_hp=os_["hp"],
            challenger_max=cs["hp"], opponent_max=os_["hp"],
            current_turn=challenger_id,
        )
        cls._pvp[challenger_id] = session
        cls._pvp[opponent_id]   = session
        return session

    @classmethod
    def get_pvp(cls, user_id: str) -> Optional[PvPSession]:
        return cls._pvp.get(user_id)

    @classmethod
    def end_pvp(cls, session: PvPSession):
        cls._pvp.pop(session.challenger_id, None)
        cls._pvp.pop(session.opponent_id,   None)


# ── Move definitions ───────────────────────────────────────────────────────
MOVES: dict[str, dict] = {
    "slash":         {"label": "⚔️ Slash",          "dmg": (40, 70),  "miss": 0.10, "desc": "slashes at the nape!"},
    "odm_dash":      {"label": "🪺 ODM Dash",        "dmg": (25, 55),  "miss": 0.05, "desc": "dashes in on ODM gear!"},
    "thunder_spear": {"label": "💥 Thunder Spear",   "dmg": (60, 100), "miss": 0.20, "desc": "fires a Thunder Spear!"},
    "spiral_cut":    {"label": "🌀 Spiral Cut",      "dmg": (35, 65),  "miss": 0.12, "desc": "performs a spiral cut!"},
    "titan_smash":   {"label": "🧱 Titan Smash",     "dmg": (55, 90),  "miss": 0.18, "desc": "unleashes a titan smash!"},
    "defend":        {"label": "🛡️ Defend",          "dmg": (0,  0),   "miss": 0.00, "desc": "takes a defensive stance!"},
}


def calc_move(move_key: str, attacker_is_scout: bool) -> tuple[int, bool, str]:
    move = MOVES.get(move_key, MOVES["slash"])
    missed = random.random() < move["miss"]
    if missed:
        return 0, True, move["desc"]
    lo, hi = move["dmg"]
    return random.randint(lo, hi), False, move["desc"]


def titan_ai_move() -> tuple[int, bool, str]:
    moves = {
        "stomp":          {"dmg": (30, 65), "miss": 0.10, "label": "🧱 stomps the ground!"},
        "swipe":          {"dmg": (25, 55), "miss": 0.08, "label": "👊 swipes with a massive arm!"},
        "boulder_throw":  {"dmg": (50, 85), "miss": 0.22, "label": "🪨 hurls a boulder!"},
        "roar":           {"dmg": (15, 30), "miss": 0.05, "label": "🗣️ unleashes a devastating roar!"},
        "crystal_harden": {"dmg": (40, 70), "miss": 0.15, "label": "💎 uses crystal hardening!"},
    }
    key = random.choice(list(moves.keys()))
    m   = moves[key]
    missed = random.random() < m["miss"]
    lo, hi = m["dmg"]
    dmg = 0 if missed else random.randint(lo, hi)
    return dmg, missed, m["label"]


def pvp_titan_attack(attacker_titan: str, defender_titan: str) -> tuple[int, bool, str]:
    """Calculate PvP attack damage based on titan stats."""
    a_stats = TITAN_STATS.get(attacker_titan, {"atk": 60, "def": 50, "spd": 60})
    d_stats = TITAN_STATS.get(defender_titan, {"atk": 60, "def": 50, "spd": 60})
    # miss based on speed difference
    miss_chance = max(0.05, 0.15 - (a_stats["spd"] - d_stats["spd"]) * 0.001)
    if random.random() < miss_chance:
        return 0, True, "attacks but MISSES!"
    base = random.randint(int(a_stats["atk"] * 0.7), a_stats["atk"])
    defense_reduction = int(d_stats["def"] * 0.3)
    dmg = max(10, base - defense_reduction)
    actions = ["charges forward!", "unleashes a powerful strike!", "attacks fiercely!",
               "launches a devastating blow!", "rushes in for the attack!"]
    return dmg, False, random.choice(actions)
