"""In-memory game state manager (replace with SQLite for persistence)."""
from __future__ import annotations
import json, os, random
from dataclasses import dataclass, field, asdict
from typing import Optional

DATA_FILE = "data/player_data.json"

RANKS = ["Cadet", "Scout", "Elite", "Captain", "Legend"]
XP_PER_LEVEL = 120

CHARACTERS = [
    "Eren Yeager", "Mikasa Ackerman", "Levi Ackerman",
    "Armin Arlert", "Hange Zoe", "Erwin Smith",
    "Reiner Braun", "Annie Leonhart", "Bertholdt Hoover",
]

TITANS = [
    "Armored Titan", "Colossal Titan", "Female Titan",
    "Beast Titan", "War Hammer Titan", "Cart Titan",
    "Jaw Titan", "Attack Titan", "Founding Titan",
]


@dataclass
class PlayerData:
    user_id: str
    username: str
    scout_name: str = "Eren Yeager"
    level: int = 1
    xp: int = 0
    wins: int = 0
    losses: int = 0
    kills: int = 0

    @property
    def xp_needed(self) -> int:
        return self.level * XP_PER_LEVEL

    @property
    def rank(self) -> str:
        idx = min(self.level // 5, len(RANKS) - 1)
        return RANKS[idx]

    def add_xp(self, amount: int) -> bool:
        """Returns True if levelled up."""
        self.xp += amount
        levelled = False
        while self.xp >= self.xp_needed:
            self.xp -= self.xp_needed
            self.level += 1
            levelled = True
        return levelled


@dataclass
class BattleSession:
    player_id: str
    scout_name: str
    titan_name: str
    scout_hp: int
    scout_max_hp: int
    titan_hp: int
    titan_max_hp: int
    round_num: int = 1
    active: bool = True
    last_action: str = ""
    channel_id: Optional[int] = None


class GameState:
    _players: dict[str, PlayerData] = {}
    _battles: dict[str, BattleSession] = {}

    @classmethod
    def _load(cls):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE) as f:
                    raw = json.load(f)
                for uid, d in raw.items():
                    cls._players[uid] = PlayerData(**d)
            except Exception:
                pass

    @classmethod
    def _save(cls):
        os.makedirs("data", exist_ok=True)
        with open(DATA_FILE, "w") as f:
            json.dump({uid: asdict(p) for uid, p in cls._players.items()}, f, indent=2)

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
    def start_battle(cls, player_id: str, scout_name: str,
                     titan_name: str, channel_id: int) -> BattleSession:
        # HP scaled by titan name difficulty
        titan_hp_map = {
            "Founding Titan": 500, "Colossal Titan": 450, "War Hammer Titan": 400,
            "Beast Titan": 380, "Armored Titan": 360, "Attack Titan": 320,
            "Female Titan": 300, "Jaw Titan": 260, "Cart Titan": 240,
        }
        scout_hp_map = {
            "Levi Ackerman": 320, "Mikasa Ackerman": 300, "Erwin Smith": 280,
            "Hange Zoe": 260, "Eren Yeager": 280, "Armin Arlert": 240,
            "Reiner Braun": 300, "Annie Leonhart": 290, "Bertholdt Hoover": 280,
        }
        s_hp  = scout_hp_map.get(scout_name, 280)
        t_hp  = titan_hp_map.get(titan_name, 300)
        session = BattleSession(
            player_id=player_id,
            scout_name=scout_name,
            titan_name=titan_name,
            scout_hp=s_hp, scout_max_hp=s_hp,
            titan_hp=t_hp, titan_max_hp=t_hp,
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


# Move actions
MOVES = {
    "slash":      {"label": "\u2694\ufe0f Slash",         "dmg": (40,70),  "miss": 0.10, "desc": "slashes at the nape!"},
    "odm_dash":   {"label": "\U0001fa7a ODM Dash",       "dmg": (25,55),  "miss": 0.05, "desc": "dashes in on ODM gear!"},
    "thunder_spear": {"label": "\U0001f4a5 Thunder Spear","dmg": (60,100), "miss": 0.20, "desc": "fires a Thunder Spear!"},
    "spiral_cut": {"label": "\U0001f300 Spiral Cut",     "dmg": (35,65),  "miss": 0.12, "desc": "performs a spiral cut!"},
    "titan_smash":{"label": "\U0001f9f1 Titan Smash",    "dmg": (55,90),  "miss": 0.18, "desc": "unleashes a titan smash!"},
    "defend":     {"label": "\U0001f6e1\ufe0f Defend",   "dmg": (0, 0),   "miss": 0.00, "desc": "takes a defensive stance!"},
}


def calc_move(move_key: str, attacker_is_scout: bool) -> tuple[int, bool, str]:
    """Returns (damage, missed, description)."""
    move = MOVES.get(move_key, MOVES["slash"])
    missed = random.random() < move["miss"]
    if missed:
        return 0, True, move["desc"]
    lo, hi = move["dmg"]
    dmg = random.randint(lo, hi)
    return dmg, False, move["desc"]


def titan_ai_move() -> str:
    """Pick a random titan move."""
    titan_moves = {
        "stomp":        {"dmg": (30,65), "miss": 0.10},
        "swipe":        {"dmg": (25,55), "miss": 0.08},
        "boulder_throw":{"dmg": (50,85), "miss": 0.22},
        "roar":         {"dmg": (15,30), "miss": 0.05},
        "crystal_harden":{"dmg":(40,70), "miss": 0.15},
    }
    key = random.choice(list(titan_moves.keys()))
    m = titan_moves[key]
    missed = random.random() < m["miss"]
    lo, hi = m["dmg"]
    dmg = 0 if missed else random.randint(lo, hi)
    labels = {
        "stomp": "\U0001f9f1 stomps the ground!",
        "swipe": "\U0001f44a swipes with a massive arm!",
        "boulder_throw": "\U0001faa8 hurls a boulder!",
        "roar": "\U0001f5e3\ufe0f unleashes a devastating roar!",
        "crystal_harden": "\U0001f48e uses crystal hardening!",
    }
    return dmg, missed, labels.get(key, "attacks!")
