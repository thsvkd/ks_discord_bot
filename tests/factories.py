"""테스트용 도메인 객체 팩토리.

정적 데이터 덩어리 대신, 필요한 필드만 덮어쓸 수 있는 팩토리를 제공한다.
"""

from __future__ import annotations

import math
from typing import Any

from ks_bot.common.enums import GameMode, MatchType
from ks_bot.common.models import Player, PlayerMatchStats

ACCOUNT_ID = 'account.1ed1250b36304678ae706a0c5fa18f64'
NORMALIZED_ID = '1ed1250b36304678ae706a0c5fa18f64'
MATCH_IDS = [
    'f6a69afd-fb60-45da-8b40-a2e013db0f33',
    '456ad743-389e-44e1-9da4-18fb12ea54de',
    'bdae2395-0552-49bb-b543-3c3b33e758f4',
    '7cbaf996-cc3f-426b-bba4-ba5920da75d0',
    '4c8e3260-6cf1-47bb-9072-6ec1959c7b90',
]


def make_player(name: str = 'example_player_1', *, match_count: int = 5, **overrides: Any) -> Player:
    player = Player(
        id=ACCOUNT_ID,
        normalized_id=NORMALIZED_ID,
        name=name,
        platform='steam',
        ban_type='Innocent',
        clan_id='clan.fab1814f906d49b08d77b3adb783cc24',
        match_list=[{'type': 'match', 'id': match_id} for match_id in MATCH_IDS[:match_count]],
    )
    for key, value in overrides.items():
        setattr(player, key, value)
    return player


def make_match_stats(
    player_name: str = 'example_player_1',
    match_id: str = MATCH_IDS[0],
    **overrides: Any,
) -> PlayerMatchStats:
    stats = PlayerMatchStats(
        player_name=player_name,
        match_id=match_id,
        is_custom_match=False,
        game_mode=GameMode.SQUAD,
        match_type=MatchType.NORMAL,
        DBNOs=3,
        boosts=4,
        damage_dealt=250.5,
        death_type='byplayer',
        headshot_kills=1,
        heals=2,
        win_place=5,
        kill_place=10,
        kill_streaks=1,
        kills=3,
        assists=2,
        longest_kill=120.5,
        revives=1,
        ride_distance=1500.0,
        swim_distance=10.0,
        walk_distance=2000.0,
        road_kills=0,
        team_kills=0,
        time_survived=1200,
        vehicle_destroys=0,
        weapons_acquired=6,
    )
    for key, value in overrides.items():
        setattr(stats, key, value)
    return stats


# docs/scoring-design.md §13의 검증 시나리오 페르소나. revives/team_kills/death_type은 전부 고정값.
_SCORE_PERSONAS: dict[str, dict[str, Any]] = {
    'rookie': {'win_place': 19, 'damage_dealt': 80.0, 'kills': 0, 'DBNOs': 0, 'assists': 0, 'time_survived': 500, 'kill_place': 75},
    'average': {'win_place': 11, 'damage_dealt': 230.0, 'kills': 2, 'DBNOs': 2, 'assists': 1, 'time_survived': 1100, 'kill_place': 35},
    'skilled': {'win_place': 4, 'damage_dealt': 450.0, 'kills': 4, 'DBNOs': 5, 'assists': 2, 'time_survived': 1500, 'kill_place': 8},
    'pro': {'win_place': 2, 'damage_dealt': 700.0, 'kills': 7, 'DBNOs': 8, 'assists': 2, 'time_survived': 1700, 'kill_place': 3},
}

PERSONA_HEADSHOT_RATIO = 0.20  # 페르소나의 누적 헤드샷 비율. 킬이 있는데 헤드샷이 0인 표본은 비현실적이라 기준선과 같은 값을 준다(§13).


def _distribute_headshots(kills_per_match: int, count: int, ratio: float = PERSONA_HEADSHOT_RATIO) -> list[int]:
    """`count`판 누적 헤드샷 비율이 `ratio`가 되도록 매치별 헤드샷 킬을 정수로 배분한다.

    매치당 킬이 한 자릿수라 판마다 같은 정수를 주면 비율이 0이나 0.5로 튄다.
    누적 기준으로 나눠 담아야 표본 전체의 비율이 의도한 값에 정확히 맞는다.
    """
    counts: list[int] = []
    previous = 0
    for index in range(1, count + 1):
        cumulative = math.floor(index * kills_per_match * ratio + 1e-9)
        counts.append(cumulative - previous)
        previous = cumulative
    return counts


def make_match_stats_profile(profile: str, count: int = 10, **overrides: Any) -> list[PlayerMatchStats]:
    """실력 페르소나(`'rookie'`/`'average'`/`'skilled'`/`'pro'`)의 매치 스탯을 `count`건 복제해 만든다.

    `headshot_kills`만 판마다 다르다(누적 비율을 `PERSONA_HEADSHOT_RATIO`에 맞추기 위해서다).
    헤드샷은 매치 점수에 들어가지 않고 집계 단계에서만 쓰이므로 §13.1/§13.2 수치에는 영향이 없다.
    """
    fields = {
        **_SCORE_PERSONAS[profile],
        'revives': 0,
        'team_kills': 0,
        'death_type': 'byplayer',
        **overrides,
    }
    headshots = _distribute_headshots(int(fields['kills']), count)
    return [make_match_stats(match_id=f'{profile}-{i}', **{'headshot_kills': headshots[i], **fields}) for i in range(count)]


def make_season_payload(season_id: str = 'division.bro.official.pc-2018-01') -> dict:
    """`seasons` 응답 중 현재 시즌 엔트리가 포함된 페이로드를 만든다."""
    return {'data': [{'type': 'season', 'id': season_id, 'attributes': {'isCurrentSeason': True}}]}


def make_ranked_stats_payload(*, tier: str = 'gold', sub_tier: int = 3, rank_point: int = 2500) -> dict:
    """`players/{id}/seasons/{season}/ranked` 응답 중 squad 통계를 포함한 페이로드를 만든다."""
    return {
        'data': {
            'type': 'rankedplayerstats',
            'attributes': {
                'rankedGameModeStats': {
                    'squad': {
                        'currentTier': {'tier': tier, 'subTier': sub_tier},
                        'currentRankPoint': rank_point,
                        'roundsPlayed': 20,
                        'avgRank': 10.0,
                        'top10Ratio': 0.3,
                        'winRatio': 0.1,
                        'damageDealt': 200.0,
                        'kills': 2,
                        'assists': 1,
                        'deaths': 15,
                        'kda': 0.2,
                    }
                }
            },
        }
    }


def make_match_payload(match_id: str, player_name: str, *, game_mode: str = 'squad', match_type: str = 'official', win_place: int = 5) -> dict:
    """`matches/{id}` 응답과 같은 형태의 페이로드를 만든다."""
    return {
        'data': {
            'type': 'match',
            'id': match_id,
            'attributes': {
                'isCustomMatch': False,
                'gameMode': game_mode,
                'matchType': match_type,
                'mapName': 'Baltic_Main',
                'duration': 1800,
                'seasonState': 'progress',
                'createdAt': '2024-01-01T00:00:00Z',
            },
        },
        'included': [
            {
                'type': 'participant',
                'attributes': {
                    'stats': {
                        'name': player_name,
                        'DBNOs': 3,
                        'boosts': 4,
                        'damageDealt': 250.5,
                        'deathType': 'byplayer',
                        'headshotKills': 1,
                        'heals': 2,
                        'winPlace': win_place,
                        'killPlace': 10,
                        'killStreaks': 1,
                        'kills': 3,
                        'assists': 2,
                        'longestKill': 120.5,
                        'revives': 1,
                        'rideDistance': 1500.0,
                        'swimDistance': 10.0,
                        'walkDistance': 2000.0,
                        'roadKills': 0,
                        'teamKills': 0,
                        'timeSurvived': 1200,
                        'vehicleDestroys': 0,
                        'weaponsAcquired': 6,
                    }
                },
            },
            {'type': 'asset', 'attributes': {}},
        ],
    }


def make_player_payload(name: str = 'example_player_1', *, match_count: int = 5) -> dict:
    """`players` 응답의 단일 플레이어 객체."""
    return {
        'type': 'player',
        'id': ACCOUNT_ID,
        'attributes': {'name': name, 'shardId': 'steam', 'banType': 'Innocent', 'clanId': 'clan.abc'},
        'relationships': {
            'matches': {
                'data': [{'type': 'match', 'id': match_id} for match_id in MATCH_IDS[:match_count]] + [{'type': 'asset', 'id': 'ignored'}],
            }
        },
    }
