from dataclasses import dataclass, field
from .enum import GameMode, MatchType, Tier


@dataclass
class Match:
    id: str = ''
    is_custom_match: bool = False
    game_mode: GameMode = GameMode.UNDEFINED
    match_type: MatchType = MatchType.UNDEFINED
    participants: list = field(default_factory=list)

    def find_player_stats_info(self, player_name: str) -> dict:
        for participant in self.participants:
            if participant['attributes']['stats']['name'] == player_name:
                return participant['attributes']['stats']
        else:
            return {}


@dataclass
class Player:
    id: str = ''
    normalized_id: str = ''
    name: str = ''
    is_updated: bool = False
    platform: str = ''
    ban_type: str = ''
    clan_id: str = ''
    rank_stats: dict = field(default_factory=dict)
    normal_stats: dict = field(default_factory=dict)
    stats_score: float = 0.0


@dataclass
class PlayerMatchStats:
    player_name: str = ''
    DBNOs: int = 0
    boosts: int = 0
    damage_dealt: float = 0.0
    death_type: str = ''
    headshot_kills: int = 0
    heals: int = 0
    win_place: int = 0
    kill_place: int = 0
    kill_streaks: int = 0
    kills: int = 0
    assists: int = 0
    longest_kill: float = 0.0
    revives: int = 0
    ride_distance: float = 0.0
    swim_distance: float = 0.0
    walk_distance: float = 0.0
    road_kills: int = 0
    team_kills: int = 0
    time_survived: int = 0
    vehicle_destroys: int = 0
    weapons_acquired: int = 0


@dataclass
class Stats:
    type: MatchType = MatchType.UNDEFINED
    tier: int = Tier.UNDEFINED
    sub_tier: int = 0
    rank_point: int = 0
    rounds_played: int = 0
    avg_rank: float = 0.0
    top10_ratio: float = 0.0
    win_ratio: float = 0.0
    damage_dealt: float = 0.0
    _avg_dealt: float = 0.0
    kills: int = 0
    assists: int = 0
    deaths: int = 0
    kda: float = 0.0
    _kd: float = 0.0

    @property
    def avg_dealt(self) -> float:
        try:
            return self.damage_dealt / self.rounds_played if self.rounds_played else 0.0
        except ZeroDivisionError:
            return 0.0

    @property
    def kd(self) -> float:
        try:
            return self.kills / self.deaths if self.deaths else 0.0
        except ZeroDivisionError:
            return 0.0
