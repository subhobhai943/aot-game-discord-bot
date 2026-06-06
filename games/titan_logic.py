from enum import Enum, auto
import random
from typing import Optional
from data.titan_images import SURVEY_CORPS_CHARACTERS, TITAN_IMAGES

class GameState(Enum):
    LOBBY = auto()
    EXPLORATION = auto()  # Mission phase
    DISCUSSION = auto()   # Meeting phase
    VOTING = auto()       # Vote phase
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
        self.missions_completed: int = 0

    def __repr__(self):
        return f"<Player {self.user_id} {self.role}>"

class TitanGameEngine:
    MIN_PLAYERS = 4
    MAX_PLAYERS = 12

    def __init__(self, guild_id: int, channel_id: int, host_id: int):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.host_id = host_id
        self.players: dict[int, Player] = {}
        self.state: GameState = GameState.LOBBY
        self.shifter_count = 1
        
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
        if user_id in self.players:
            del self.players[user_id]
            if user_id == self.host_id and self.players:
                self.host_id = list(self.players.keys())[0]
            return True
        return False

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
        titan_types = [t for t in TITAN_IMAGES.keys() if t not in ("Pure Titan", "Abnormal Titan", "Transformation", "Smiling Titan")]
        random.shuffle(titan_types)

        for uid in player_ids:
            p = self.players[uid]
            if uid in shifters:
                p.role = Role.TITAN_SHIFTER
                ttype = titan_types.pop() if titan_types else "Attack Titan"
                p.character_name = ttype
                p.image_url = random.choice(TITAN_IMAGES[ttype]) if TITAN_IMAGES.get(ttype) else ""
            else:
                p.role = Role.SURVEY_CORPS
                p.character_name = sc_chars.pop()
                p.image_url = ""

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
            
        target.is_alive = False
        return True, f"You have devoured {target.character_name}."

    def call_meeting(self, caller_id: int) -> bool:
        if self.state != GameState.EXPLORATION:
            return False
        caller = self.players.get(caller_id)
        if not caller or not caller.is_alive:
            return False
            
        self.state = GameState.DISCUSSION
        for p in self.players.values():
            p.has_voted = False
            p.voted_for = None
        return True

    def start_voting(self) -> bool:
        if self.state != GameState.DISCUSSION:
            return False
        self.state = GameState.VOTING
        return True

    def vote(self, voter_id: int, target_id: Optional[int]) -> tuple[bool, str]:
        if self.state != GameState.VOTING:
            return False, "It's not voting time."
        voter = self.players.get(voter_id)
        if not voter or not voter.is_alive:
            return False, "You cannot vote."
        if voter.has_voted:
            return False, "You have already voted."
        
        if target_id is not None and target_id not in self.players:
            return False, "Target is not in the game."

        voter.has_voted = True
        voter.voted_for = target_id
        return True, "Vote cast."

    def get_vote_results(self) -> tuple[Optional[int], bool]:
        tally: dict[Optional[int], int] = {}
        for p in self.players.values():
            if p.has_voted:
                tally[p.voted_for] = tally.get(p.voted_for, 0) + 1
                
        if not tally:
            return None, False
            
        max_votes = max(tally.values())
        candidates = [uid for uid, v in tally.items() if v == max_votes]
        
        if len(candidates) > 1:
            return None, True # Tie
            
        exiled = candidates[0]
        if exiled:
            ep = self.players.get(exiled)
            if ep:
                ep.is_alive = False
        return exiled, False

    def check_win(self) -> Optional[Role]:
        alive_shifters = sum(1 for p in self.players.values() if p.is_alive and p.role == Role.TITAN_SHIFTER)
        alive_sc = sum(1 for p in self.players.values() if p.is_alive and p.role == Role.SURVEY_CORPS)
        
        if alive_shifters == 0:
            return Role.SURVEY_CORPS
        if alive_shifters >= alive_sc:
            return Role.TITAN_SHIFTER
            
        return None
