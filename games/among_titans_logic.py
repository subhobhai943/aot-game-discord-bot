from enum import Enum, auto
import random
from typing import Optional

from data.titan_images import SURVEY_CORPS_CHARACTERS, TITAN_IMAGES

class GameState(Enum):
    LOBBY = auto()
    NIGHT = auto()      # Action phase
    MEETING = auto()    # Discussion phase
    VOTING = auto()     # Voting phase
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

    def __repr__(self):
        return f"<Player {self.user_id} {self.role}>"


class AmongTitansGame:
    MIN_PLAYERS = 3

    def __init__(self, guild_id: int, channel_id: int, host_id: int):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.host_id = host_id
        self.players: dict[int, Player] = {}
        self.state: GameState = GameState.LOBBY
        self.shifter_count = 1
        
        self.add_player(host_id)

    def add_player(self, user_id: int) -> bool:
        if self.state != GameState.LOBBY:
            return False
        if user_id in self.players:
            return False
        self.players[user_id] = Player(user_id)
        return True

    def remove_player(self, user_id: int) -> bool:
        if user_id in self.players:
            del self.players[user_id]
            if user_id == self.host_id and self.players:
                self.host_id = list(self.players.keys())[0] # Re-assign host
            return True
        return False

    def start_game(self) -> bool:
        if len(self.players) < self.MIN_PLAYERS:
            return False
            
        if len(self.players) >= 7:
            self.shifter_count = 2
        else:
            self.shifter_count = 1

        player_ids = list(self.players.keys())
        shifters = random.sample(player_ids, self.shifter_count)
        
        # Pick unique characters
        sc_chars = random.sample(SURVEY_CORPS_CHARACTERS, len(player_ids))
        titan_types = list(TITAN_IMAGES.keys())
        random.shuffle(titan_types)

        for uid in player_ids:
            p = self.players[uid]
            if uid in shifters:
                p.role = Role.TITAN_SHIFTER
                ttype = titan_types.pop()
                p.character_name = ttype
                p.image_url = random.choice(TITAN_IMAGES[ttype])
            else:
                p.role = Role.SURVEY_CORPS
                p.character_name = sc_chars.pop()
                p.image_url = "" # Can use a default or none

        self.state = GameState.NIGHT
        return True

    def eliminate(self, shifter_id: int, target_id: int) -> bool:
        if self.state != GameState.NIGHT:
            return False
        
        shifter = self.players.get(shifter_id)
        target = self.players.get(target_id)
        
        if not shifter or not target:
            return False
        if shifter.role != Role.TITAN_SHIFTER or not shifter.is_alive:
            return False
        if not target.is_alive or target.role == Role.TITAN_SHIFTER:
            return False
            
        target.is_alive = False
        return True

    def report(self, reporter_id: int) -> bool:
        if self.state != GameState.NIGHT:
            return False
        reporter = self.players.get(reporter_id)
        if not reporter or not reporter.is_alive:
            return False
            
        self.state = GameState.MEETING
        # Reset votes
        for p in self.players.values():
            p.has_voted = False
            p.voted_for = None
        return True

    def start_voting(self) -> bool:
        if self.state != GameState.MEETING:
            return False
        self.state = GameState.VOTING
        return True

    def vote(self, voter_id: int, target_id: Optional[int]) -> bool:
        if self.state != GameState.VOTING:
            return False
        voter = self.players.get(voter_id)
        if not voter or not voter.is_alive or voter.has_voted:
            return False
            
        voter.has_voted = True
        voter.voted_for = target_id
        return True

    def get_vote_results(self) -> tuple[Optional[int], bool]:
        """Returns (exiled_user_id, is_tie)"""
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
