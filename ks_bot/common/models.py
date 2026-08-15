"""PUBG 도메인 모델.

PUBG API의 JSON 응답을 파싱하는 책임은 각 모델의 `from_api()` 팩토리가 가진다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ks_bot.common.enums import GameMode, MatchType, Tier
from ks_bot.common.errors import PlayerMatchStatsNotFoundError
from ks_bot.common.timeutil import parse_utc_to_datetime, unix_time_start

__all__ = ['Match', 'Player', 'PlayerMatchStats', 'Stats']


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


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
    match_list: list[dict] = field(default_factory=list)

    @property
    def match_ids(self) -> list[str]:
        """최신순으로 정렬된 매치 ID 목록."""
        return [match['id'] for match in self.match_list if 'id' in match]

    @classmethod
    def from_api(cls, data: dict) -> Player:
        """`players` 엔드포인트의 단일 플레이어 객체를 파싱한다."""
        attributes = data.get('attributes', {})
        matches = data.get('relationships', {}).get('matches', {}).get('data', [])
        player_id = data.get('id', '')
        return cls(
            id=player_id,
            normalized_id=normalize_player_id(player_id),
            name=attributes.get('name', ''),
            platform=attributes.get('shardId', ''),
            ban_type=attributes.get('banType', ''),
            clan_id=attributes.get('clanId', '') or '',
            match_list=[match for match in matches if match.get('type') == 'match'],
        )


def normalize_player_id(player_id: str) -> str:
    """`account.<hex>` 또는 UUID 형태의 플레이어 ID를 하이픈 없는 형태로 정규화한다."""
    if not player_id:
        return ''
    if player_id.startswith('account.'):
        player_id = player_id.split('.', 1)[1]
    return player_id.replace('-', '')


@dataclass
class PlayerMatchStats:
    player_name: str = ''
    match_id: str = ''
    is_custom_match: bool = False
    game_mode: GameMode = GameMode.UNDEFINED
    match_type: MatchType = MatchType.UNDEFINED
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

    @classmethod
    def from_api(cls, stats: dict, *, match: Match) -> PlayerMatchStats:
        return cls(
            player_name=stats.get('name', ''),
            match_id=match.id,
            is_custom_match=match.is_custom_match,
            game_mode=match.game_mode,
            match_type=match.match_type,
            DBNOs=_to_int(stats.get('DBNOs')),
            boosts=_to_int(stats.get('boosts')),
            damage_dealt=_to_float(stats.get('damageDealt')),
            death_type=stats.get('deathType', ''),
            headshot_kills=_to_int(stats.get('headshotKills')),
            heals=_to_int(stats.get('heals')),
            win_place=_to_int(stats.get('winPlace')),
            kill_place=_to_int(stats.get('killPlace')),
            kill_streaks=_to_int(stats.get('killStreaks')),
            kills=_to_int(stats.get('kills')),
            assists=_to_int(stats.get('assists')),
            longest_kill=_to_float(stats.get('longestKill')),
            revives=_to_int(stats.get('revives')),
            ride_distance=_to_float(stats.get('rideDistance')),
            swim_distance=_to_float(stats.get('swimDistance')),
            walk_distance=_to_float(stats.get('walkDistance')),
            road_kills=_to_int(stats.get('roadKills')),
            team_kills=_to_int(stats.get('teamKills')),
            time_survived=_to_int(stats.get('timeSurvived')),
            vehicle_destroys=_to_int(stats.get('vehicleDestroys')),
            weapons_acquired=_to_int(stats.get('weaponsAcquired')),
        )


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
    participants: list[dict] = field(default_factory=list)

    @classmethod
    def from_api(cls, match_id: str, payload: dict) -> Match:
        """`matches/{id}` 응답을 파싱한다."""
        attributes = payload.get('data', {}).get('attributes', {})
        included = payload.get('included', [])
        return cls(
            id=match_id,
            is_custom_match=bool(attributes.get('isCustomMatch', False)),
            game_mode=GameMode.from_string(attributes.get('gameMode', '')),
            match_type=MatchType.from_string(attributes.get('matchType', '')),
            map_name=attributes.get('mapName', ''),
            duration=_to_int(attributes.get('duration')),
            season_state=attributes.get('seasonState', ''),
            date=parse_utc_to_datetime(attributes.get('createdAt', '1970-01-01T00:00:00Z')),
            participants=[item for item in included if item.get('type') == 'participant'],
        )

    def player_stats(self, player_name: str) -> PlayerMatchStats:
        """매치 참가자 중 해당 플레이어의 전적을 반환한다.

        Raises:
            PlayerMatchStatsNotFoundError: 참가자 목록에 플레이어가 없는 경우.
        """
        for participant in self.participants:
            stats = participant.get('attributes', {}).get('stats', {})
            if stats.get('name') == player_name:
                return PlayerMatchStats.from_api(stats, match=self)

        raise PlayerMatchStatsNotFoundError(player_name=player_name, match_id=self.id)


@dataclass
class Stats:
    """집계된 플레이어 성적."""

    type: MatchType = MatchType.UNDEFINED
    tier: Tier = Tier.UNDEFINED
    sub_tier: int = 0
    rank_point: int = 0
    rounds_played: int = 0
    avg_rank: float = 0.0
    top10_ratio: float = 0.0
    win_ratio: float = 0.0
    damage_dealt: float = 0.0
    kills: int = 0
    assists: int = 0
    deaths: int = 0
    kda: float = 0.0
    score: float = 0.0

    @property
    def avg_damage_dealt(self) -> float:
        return self.damage_dealt / self.rounds_played if self.rounds_played else 0.0

    @property
    def kd(self) -> float:
        return self.kills / self.deaths if self.deaths else float(self.kills)

    @classmethod
    def from_ranked_api(cls, squad_stats: dict) -> Stats:
        """`players/{id}/seasons/{season}/ranked` 응답의 squad 통계를 파싱한다."""
        current_tier = squad_stats.get('currentTier', {})
        return cls(
            type=MatchType.RANKED,
            tier=Tier.from_string(current_tier.get('tier', '')),
            sub_tier=_to_int(current_tier.get('subTier')),
            rank_point=_to_int(squad_stats.get('currentRankPoint')),
            rounds_played=_to_int(squad_stats.get('roundsPlayed')),
            avg_rank=_to_float(squad_stats.get('avgRank')),
            top10_ratio=_to_float(squad_stats.get('top10Ratio')),
            win_ratio=_to_float(squad_stats.get('winRatio')),
            damage_dealt=_to_float(squad_stats.get('damageDealt')),
            kills=_to_int(squad_stats.get('kills')),
            assists=_to_int(squad_stats.get('assists')),
            deaths=_to_int(squad_stats.get('deaths')),
            kda=_to_float(squad_stats.get('kda')),
        )
