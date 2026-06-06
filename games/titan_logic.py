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
        self.next_kill_at: float = 0.0
        self.meetings_called: int = 0
        # Per-game assigned puzzle tasks (indices into AOT_PUZZLE_TASKS)
        self.assigned_task_indices: list[int] = []
        self.current_task_index: int = 0  # which assigned task they're on next

    def __repr__(self) -> str:
        return f"<Player {self.user_id} {self.role}>"


class TitanGameEngine:
    MIN_PLAYERS = 4
    MAX_PLAYERS = 12
    TASKS_PER_PLAYER = 3
    KILL_COOLDOWN_SECONDS = 45
    VOTE_DURATION_SECONDS = 60

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

        self.add_player(host_id)

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
        return [player for player in self.players.values() if player.is_alive]

    def alive_survey_corps(self) -> list[Player]:
        return [
            player for player in self.players.values()
            if player.is_alive and player.role == Role.SURVEY_CORPS
        ]

    def alive_shifters(self) -> list[Player]:
        return [
            player for player in self.players.values()
            if player.is_alive and player.role == Role.TITAN_SHIFTER
        ]

    def get_task_progress(self) -> tuple[int, int]:
        completed = 0
        required = 0
        for player in self.players.values():
            if player.role != Role.SURVEY_CORPS or not player.is_alive:
                continue
            completed += min(player.tasks_completed, self.TASKS_PER_PLAYER)
            required += self.TASKS_PER_PLAYER
        return completed, required

    def are_survey_tasks_complete(self) -> bool:
        for player in self.players.values():
            if player.role == Role.SURVEY_CORPS and player.is_alive:
                if player.tasks_completed < self.TASKS_PER_PLAYER:
                    return False
        return True

    def seconds_until_kill(self, shifter_id: int) -> int:
        player = self.players.get(shifter_id)
        if not player:
            return 0
        remaining = max(0.0, player.next_kill_at - time.monotonic())
        return int(remaining + 0.999)

    def get_vote_time_remaining(self) -> int:
        if self.state != GameState.VOTING or self.vote_started_at is None:
            return 0
        elapsed = time.monotonic() - self.vote_started_at
        remaining = max(0.0, self.VOTE_DURATION_SECONDS - elapsed)
        return int(remaining + 0.999)

    def assign_tasks_to_player(self, player: Player, all_task_count: int):
        """Assign TASKS_PER_PLAYER unique task indices to a player."""
        indices = list(range(all_task_count))
        random.shuffle(indices)
        player.assigned_task_indices = indices[:self.TASKS_PER_PLAYER]
        player.current_task_index = 0

    def start_game(self) -> tuple[bool, str]:
        if len(self.players) < self.MIN_PLAYERS:
            return False, f"Not enough players. Need at least {self.MIN_PLAYERS}."

        count = len(self.players)
        if count <= 6:
            self.shifter_count = 1
        elif count <= 9:
            self.shifter_count = 2
        else:
            self.shifter_count = 3

        player_ids = list(self.players.keys())
        shifters = random.sample(player_ids, self.shifter_count)

        sc_chars = random.sample(SURVEY_CORPS_CHARACTERS, len(player_ids))
        titan_types = [
            titan_name
            for titan_name in TITAN_IMAGES.keys()
            if titan_name not in ("Pure Titan", "Abnormal Titan", "Transformation", "Smiling Titan")
        ]
        random.shuffle(titan_types)

        from cogs.titan_game import AOT_PUZZLE_TASKS  # imported here to avoid circular
        task_count = len(AOT_PUZZLE_TASKS)

        for user_id in player_ids:
            player = self.players[user_id]
            player.is_alive = True
            player.has_voted = False
            player.voted_for = None
            player.tasks_completed = 0
            player.next_kill_at = 0.0
            player.meetings_called = 0

            if user_id in shifters:
                player.role = Role.TITAN_SHIFTER
                titan_type = titan_types.pop() if titan_types else "Attack Titan"
                player.character_name = titan_type
                player.image_url = random.choice(TITAN_IMAGES[titan_type]) if TITAN_IMAGES.get(titan_type) else ""
            else:
                player.role = Role.SURVEY_CORPS
                player.character_name = sc_chars.pop()
                player.image_url = ""
                self.assign_tasks_to_player(player, task_count)

        self.total_tasks_completed = 0
        self.total_tasks_required = sum(
            1 for player in self.players.values() if player.role == Role.SURVEY_CORPS
        ) * self.TASKS_PER_PLAYER
        self.vote_started_at = None
        self.state = GameState.EXPLORATION
        return True, "Started"

    def eliminate(self, shifter_id: int, target_id: int) -> tuple[bool, str]:
        if self.state != GameState.EXPLORATION:
            return False, "You can only eliminate during the Exploration phase."

        shifter = self.players.get(shifter_id)
        target = self.players.get(target_id)
        if not shifter or not target:
            return False, "Invalid target."
        if shifter.role != Role.TITAN_SHIFTER or not shifter.is_alive:
            return False, "You cannot do that."
        if not target.is_alive or target.role == Role.TITAN_SHIFTER:
            return False, "Invalid target."

        cooldown = self.seconds_until_kill(shifter_id)
        if cooldown > 0:
            return False, f"Your titan power is recovering. Wait {cooldown}s."

        target.is_alive = False
        shifter.next_kill_at = time.monotonic() + self.KILL_COOLDOWN_SECONDS
        return True, f"You devoured {target.character_name}."

    def do_task(self, player_id: int) -> tuple[bool, str]:
        if self.state != GameState.EXPLORATION:
            return False, "Tasks can only be completed during exploration."

        player = self.players.get(player_id)
        if not player or not player.is_alive:
            return False, "You cannot do tasks right now."
        if player.role == Role.TITAN_SHIFTER:
            return False, "Titan Shifters can only fake task work."
        if player.tasks_completed >= self.TASKS_PER_PLAYER:
            return False, "You have already finished every mission task."

        player.tasks_completed += 1
        player.current_task_index += 1
        self.total_tasks_completed += 1
        return True, f"Task completed. ({player.tasks_completed}/{self.TASKS_PER_PLAYER})"

    def get_next_task_index(self, player_id: int) -> Optional[int]:
        """Return the AOT_PUZZLE_TASKS index for the player's next task, or None if done."""
        player = self.players.get(player_id)
        if not player or player.role == Role.TITAN_SHIFTER:
            return None
        if player.current_task_index >= len(player.assigned_task_indices):
            return None
        return player.assigned_task_indices[player.current_task_index]

    def call_meeting(self, caller_id: int) -> bool:
        if self.state != GameState.EXPLORATION:
            return False

        caller = self.players.get(caller_id)
        if not caller or not caller.is_alive:
            return False

        self.state = GameState.DISCUSSION
        for player in self.players.values():
            player.has_voted = False
            player.voted_for = None
        return True

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
            return False, "You have already voted."

        if target_id is not None:
            target = self.players.get(target_id)
            if not target or not target.is_alive:
                return False, "That target cannot be voted out."

        voter.has_voted = True
        voter.voted_for = target_id
        return True, "Vote cast."

    def get_vote_results(self) -> tuple[Optional[int], bool]:
        tally: dict[Optional[int], int] = {}
        for player in self.players.values():
            if player.is_alive and player.has_voted:
                tally[player.voted_for] = tally.get(player.voted_for, 0) + 1

        self.vote_started_at = None
        if not tally:
            return None, False

        max_votes = max(tally.values())
        candidates = [user_id for user_id, votes in tally.items() if votes == max_votes]
        if len(candidates) > 1:
            return None, True

        exiled_id = candidates[0]
        if exiled_id is not None:
            exiled_player = self.players.get(exiled_id)
            if exiled_player:
                exiled_player.is_alive = False
        return exiled_id, False

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
