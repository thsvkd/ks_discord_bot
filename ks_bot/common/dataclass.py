from dataclasses import dataclass, field
from .enum import GameMode, MatchType, Tier
from .common import *
from .error import *
from datetime import datetime
from typing import Union


@dataclass
class Match:
    id: str = ''
    is_custom_match: bool = False
    game_mode: GameMode = GameMode.UNDEFINED
    match_type: MatchType = MatchType.UNDEFINED
    map_name: str = ''
    duration: int = 0
    season_state: str = ''
    date: datetime = field(default_factory=unix_time_start)
    participants: list = field(default_factory=list)

    def get_match_by_player_name(self, player_name: str) -> Union['PlayerMatchStats', Error_Balancer]:
        for participant in self.participants:
            if participant['attributes']['stats']['name'] == player_name:
                player_stats_info = participant['attributes']['stats']
                return PlayerMatchStats(
                    player_name=player_name,
                    match_id=self.id,
                    is_custom_match=self.is_custom_match,
                    game_mode=self.game_mode,
                    match_type=self.match_type,
                    DBNOs=player_stats_info['DBNOs'],
                    boosts=player_stats_info['boosts'],
                    damage_dealt=player_stats_info['damageDealt'],
                    death_type=player_stats_info['deathType'],
                    headshot_kills=player_stats_info['headshotKills'],
                    heals=player_stats_info['heals'],
                    win_place=player_stats_info['winPlace'],
                    kill_place=player_stats_info['killPlace'],
                    kill_streaks=player_stats_info['killStreaks'],
                    kills=player_stats_info['kills'],
                    assists=player_stats_info['assists'],
                    longest_kill=player_stats_info['longestKill'],
                    revives=player_stats_info['revives'],
                    ride_distance=player_stats_info['rideDistance'],
                    swim_distance=player_stats_info['swimDistance'],
                    walk_distance=player_stats_info['walkDistance'],
                    road_kills=player_stats_info['roadKills'],
                    team_kills=player_stats_info['teamKills'],
                    time_survived=player_stats_info['timeSurvived'],
                    vehicle_destroys=player_stats_info['vehicleDestroys'],
                    weapons_acquired=player_stats_info['weaponsAcquired'],
                )
        else:
            return PlayerMatchStatsNotFoundError_Balancer(f"Player match stats not found for {player_name} in match {self.id}.")


@dataclass
class Player:
    id: str = ''
    normalized_id: str = ''
    name: str = ''
    platform: str = ''
    ban_type: str = ''
    clan_id: str = ''
    rank_stats: dict = field(default_factory=dict)
    normal_stats: dict = field(default_factory=dict)
    match_list: list = field(default_factory=list)


@dataclass
class PlayerMatchStats:
    player_name: str = ''
    match_id: str = ''
    is_custom_match: bool = False
    game_mode: GameMode = field(default_factory=GameMode.from_string)
    match_type: MatchType = field(default_factory=MatchType.from_string)
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
    type: MatchType = field(default_factory=MatchType.from_string)
    tier: Tier = field(default_factory=Tier.from_string)
    sub_tier: int = 0
    rank_point: int = 0
    rounds_played: int = 0
    avg_rank: float = 0.0
    top10_ratio: float = 0.0
    win_ratio: float = 0.0
    damage_dealt: float = 0.0
    _avg_damage_dealt: float = 0.0
    kills: int = 0
    assists: int = 0
    deaths: int = 0
    kda: float = 0.0
    _kd: float = 0.0
    score: float = 0.0

    @property
    def avg_damage_dealt(self) -> float:
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
