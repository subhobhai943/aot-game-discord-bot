from __future__ import annotations

from enum import Enum, auto
import random
import time
from typing import Optional

from data.titan_images import SURVEY_CORPS_CHARACTERS, TITAN_IMAGES


class GameState(Enum):
    LOBBY = auto()
    EXPLORATION = auto()
    DISCUSSION = auto()
    VOTING = auto()
    GAME_OVER = auto()


class Role(Enum):
    SURVEY_CORPS = "Survey Corps Member"
    TITAN_SHIFTER = "Titan Shifter"


class Player:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.role: Optional[Role] = None
        self.character_name: str = ""
        self.image_url: str = ""
        self.is_alive: bool = True
        self.has_voted: bool = False
        self.voted_for: Optional[int] = None
        self.tasks_completed: int = 0
        # Kill tracking — monotonic timestamp, 0.0 = ready immediately
        self.next_kill_at: float = 0.0
        self.meetings_called: int = 0
        # Per-round assigned jigsaw task indices
        self.assigned_task_indices: list[int] = []
        self.current_task_index: int = 0

    def __repr__(self) -> str:
        return f"<Player {self.user_id} {self.role}>"


class TitanGameEngine:
    MIN_PLAYERS = 4
    MAX_PLAYERS = 12
    TASKS_PER_PLAYER = 3
    KILL_COOLDOWN_SECONDS = 45
    VOTE_DURATION_SECONDS = 60
    MEETING_COOLDOWN_SECONDS = 30   # ← NEW: post-meeting cooldown before next meeting

    def __init__(self, guild_id: int, channel_id: int, host_id: int):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.game_channel_id: Optional[int] = None
        self.host_id = host_id
        self.players: dict[int, Player] = {}
        self.state: GameState = GameState.LOBBY
        self.shifter_count = 1
        self.total_tasks_completed = 0
        self.total_tasks_required = 0
        self.lobby_message_id: Optional[int] = None
        self.vote_started_at: Optional[float] = None
        # Round tracking
        self.round_number: int = 0
        # Global meeting cooldown — monotonic timestamp
        self.next_meeting_allowed_at: float = 0.0

        self.add_player(host_id)

    # ── Player management ──────────────────────────────────────────────────
    def add_player(self, user_id: int) -> tuple[bool, str]:
        if self.state != GameState.LOBBY:
            return False, "Game has already started."
        if user_id in self.players:
            return False, "You are already in the lobby."
        if len(self.players) >= self.MAX_PLAYERS:
            return False, "Lobby is full."
        self.players[user_id] = Player(user_id)
        return True, "Joined successfully."

    def remove_player(self, user_id: int) -> bool:
        if user_id not in self.players:
            return False
        del self.players[user_id]
        if user_id == self.host_id and self.players:
            self.host_id = next(iter(self.players))
        return True

    def alive_players(self) -> list[Player]:
        return [p for p in self.players.values() if p.is_alive]

    def alive_survey_corps(self) -> list[Player]:
        return [p for p in self.players.values() if p.is_alive and p.role == Role.SURVEY_CORPS]

    def alive_shifters(self) -> list[Player]:
        return [p for p in self.players.values() if p.is_alive and p.role == Role.TITAN_SHIFTER]

    # ── Task helpers ───────────────────────────────────────────────────────
    def get_task_progress(self) -> tuple[int, int]:
        completed = required = 0
        for p in self.players.values():
            if p.role != Role.SURVEY_CORPS or not p.is_alive:
                continue
            completed += min(p.tasks_completed, self.TASKS_PER_PLAYER)
            required += self.TASKS_PER_PLAYER
        return completed, required

    def are_survey_tasks_complete(self) -> bool:
        return all(
            p.tasks_completed >= self.TASKS_PER_PLAYER
            for p in self.players.values()
            if p.role == Role.SURVEY_CORPS and p.is_alive
        )

    def assign_tasks_to_player(self, player: Player, all_task_count: int) -> None:
        indices = list(range(all_task_count))
        random.shuffle(indices)
        player.assigned_task_indices = indices[: self.TASKS_PER_PLAYER]
        player.current_task_index = 0

    def get_next_task_index(self, player_id: int) -> Optional[int]:
        p = self.players.get(player_id)
        if not p or p.role == Role.TITAN_SHIFTER:
            return None
        if p.current_task_index >= len(p.assigned_task_indices):
            return None
        return p.assigned_task_indices[p.current_task_index]

    # ── Timers ─────────────────────────────────────────────────────────────
    def seconds_until_kill(self, shifter_id: int) -> int:
        p = self.players.get(shifter_id)
        if not p:
            return 0
        return max(0, int(p.next_kill_at - time.monotonic() + 0.999))

    def seconds_until_meeting(self) -> int:
        remaining = self.next_meeting_allowed_at - time.monotonic()
        return max(0, int(remaining + 0.999))

    def get_vote_time_remaining(self) -> int:
        if self.state != GameState.VOTING or self.vote_started_at is None:
            return 0
        elapsed = time.monotonic() - self.vote_started_at
        return max(0, int(self.VOTE_DURATION_SECONDS - elapsed + 0.999))

    # ── Game flow ──────────────────────────────────────────────────────────
    def start_game(self) -> tuple[bool, str]:
        if len(self.players) < self.MIN_PLAYERS:
            return False, f"Need at least {self.MIN_PLAYERS} players."

        count = len(self.players)
        self.shifter_count = 1 if count <= 6 else (2 if count <= 9 else 3)

        player_ids = list(self.players.keys())
        shifters = set(random.sample(player_ids, self.shifter_count))

        sc_chars = random.sample(SURVEY_CORPS_CHARACTERS, len(player_ids))
        titan_types = [
            t for t in TITAN_IMAGES
            if t not in ("Pure Titan", "Abnormal Titan", "Transformation", "Smiling Titan")
        ]
        random.shuffle(titan_types)

        # Avoid circular import — task count supplied by cog at start
        from cogs.titan_game import JIGSAW_TASKS
        task_count = len(JIGSAW_TASKS)

        for uid in player_ids:
            p = self.players[uid]
            p.is_alive = True
            p.has_voted = False
            p.voted_for = None
            p.tasks_completed = 0
            p.next_kill_at = 0.0        # ← BUG FIX: always reset kill cooldown on game start
            p.meetings_called = 0

            if uid in shifters:
                p.role = Role.TITAN_SHIFTER
                titan_type = titan_types.pop() if titan_types else "Attack Titan"
                p.character_name = titan_type
                p.image_url = random.choice(TITAN_IMAGES[titan_type]) if TITAN_IMAGES.get(titan_type) else ""
            else:
                p.role = Role.SURVEY_CORPS
                p.character_name = sc_chars.pop()
                p.image_url = ""
                self.assign_tasks_to_player(p, task_count)

        self.total_tasks_completed = 0
        self.total_tasks_required = (
            sum(1 for p in self.players.values() if p.role == Role.SURVEY_CORPS)
            * self.TASKS_PER_PLAYER
        )
        self.vote_started_at = None
        self.round_number = 1
        self.next_meeting_allowed_at = 0.0
        self.state = GameState.EXPLORATION
        return True, "Started"

    def eliminate(self, shifter_id: int, target_id: int) -> tuple[bool, str]:
        """BUG FIX: uses time.monotonic() correctly; view now refreshes after each kill."""
        if self.state != GameState.EXPLORATION:
            return False, "You can only eliminate during the Exploration phase."

        shifter = self.players.get(shifter_id)
        target = self.players.get(target_id)
        if not shifter or not target:
            return False, "Invalid target."
        if shifter.role != Role.TITAN_SHIFTER or not shifter.is_alive:
            return False, "You cannot use titan powers right now."
        if not target.is_alive or target.role == Role.TITAN_SHIFTER:
            return False, "Invalid target."

        cooldown = self.seconds_until_kill(shifter_id)
        if cooldown > 0:
            return False, f"⏳ Titan power recharging. Wait **{cooldown}s**."

        target.is_alive = False
        # ← BUG FIX: set ABSOLUTE monotonic timestamp, not relative — was the root cause
        shifter.next_kill_at = time.monotonic() + self.KILL_COOLDOWN_SECONDS
        return True, f"You devoured **{target.character_name}**."

    def do_task(self, player_id: int) -> tuple[bool, str]:
        if self.state != GameState.EXPLORATION:
            return False, "Tasks can only be completed during exploration."
        p = self.players.get(player_id)
        if not p or not p.is_alive:
            return False, "You cannot do tasks right now."
        if p.role == Role.TITAN_SHIFTER:
            return False, "Titan Shifters don't do real tasks."
        if p.tasks_completed >= self.TASKS_PER_PLAYER:
            return False, "You have already finished all your tasks!"

        p.tasks_completed += 1
        p.current_task_index += 1
        self.total_tasks_completed += 1
        return True, f"Task completed! ({p.tasks_completed}/{self.TASKS_PER_PLAYER})"

    def call_meeting(self, caller_id: int) -> tuple[bool, str]:
        """Returns (success, error_message). Now enforces meeting cooldown."""
        if self.state != GameState.EXPLORATION:
            return False, "You can only call a meeting during exploration."
        caller = self.players.get(caller_id)
        if not caller or not caller.is_alive:
            return False, "You cannot call a meeting."

        cooldown = self.seconds_until_meeting()
        if cooldown > 0:
            return False, f"⏳ Meeting cooldown active! Wait **{cooldown}s** before calling another."

        self.state = GameState.DISCUSSION
        for p in self.players.values():
            p.has_voted = False
            p.voted_for = None
        # Set cooldown for AFTER this meeting resolves (set in resolve_votes)
        return True, ""

    def end_meeting_set_cooldown(self) -> None:
        """Called after votes resolve to start the 30s cooldown."""
        self.next_meeting_allowed_at = time.monotonic() + self.MEETING_COOLDOWN_SECONDS

    def start_voting(self) -> bool:
        if self.state != GameState.DISCUSSION:
            return False
        self.state = GameState.VOTING
        self.vote_started_at = time.monotonic()
        return True

    def vote(self, voter_id: int, target_id: Optional[int]) -> tuple[bool, str]:
        if self.state != GameState.VOTING:
            return False, "It is not voting time."
        voter = self.players.get(voter_id)
        if not voter or not voter.is_alive:
            return False, "You cannot vote."
        if voter.has_voted:
            return False, "You already voted."
        if target_id is not None:
            target = self.players.get(target_id)
            if not target or not target.is_alive:
                return False, "That player cannot be voted out."
        voter.has_voted = True
        voter.voted_for = target_id
        return True, "Vote cast."

    def get_vote_results(self) -> tuple[Optional[int], bool]:
        tally: dict[Optional[int], int] = {}
        for p in self.players.values():
            if p.is_alive and p.has_voted:
                tally[p.voted_for] = tally.get(p.voted_for, 0) + 1
        self.vote_started_at = None
        if not tally:
            return None, False
        max_votes = max(tally.values())
        candidates = [uid for uid, v in tally.items() if v == max_votes]
        if len(candidates) > 1:
            return None, True
        exiled_id = candidates[0]
        if exiled_id is not None:
            ep = self.players.get(exiled_id)
            if ep:
                ep.is_alive = False
        return exiled_id, False

    def advance_round(self) -> None:
        self.round_number += 1

    def check_win(self) -> Optional[Role]:
        alive_shifters = len(self.alive_shifters())
        alive_survey = len(self.alive_survey_corps())
        if alive_shifters == 0:
            return Role.SURVEY_CORPS
        if alive_shifters >= alive_survey:
            return Role.TITAN_SHIFTER
        if self.are_survey_tasks_complete():
            return Role.SURVEY_CORPS
        return None
