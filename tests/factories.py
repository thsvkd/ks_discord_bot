"""테스트용 도메인 객체 팩토리.

정적 데이터 덩어리 대신, 필요한 필드만 덮어쓸 수 있는 팩토리를 제공한다.
"""

from __future__ import annotations

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
