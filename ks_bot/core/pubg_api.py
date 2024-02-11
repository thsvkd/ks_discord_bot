import asyncio
import os
from termcolor import colored, cprint
from typing import List, Dict, Union, Tuple
from datetime import datetime, timedelta

from ks_bot.core.request_handler import HttpMethod, APIRequestHandler
from ks_bot.common.error import *
from ks_bot.common.common import *
from ks_bot.common.enum import GameMode, MatchType, Tier
from ks_bot.common.dataclass import Player, Match, Stats, PlayerMatchStats
from ks_bot.core.db_handler import SQLiteDBHandler


class PUBG_Balancer:
    DEFAULT_MAX_MATCH_NUM = 20
    DEFAULT_DB_PATH = 'res/history.db'

    def __init__(self, api_key: str, platform: str = 'steam', db_init: bool = False):
        self._api_key = api_key
        self._platform = platform
        self._header = {"Authorization": f"Bearer {self._api_key}", "Accept": "application/vnd.api+json"}
        self._base_url = f'https://api.pubg.com/shards/{self._platform}'
        self._api_request_handler = APIRequestHandler(api_key=self._api_key, base_url=self._base_url)
        self._db_handler = SQLiteDBHandler(PUBG_Balancer.DEFAULT_DB_PATH)
        self._db_init = db_init

    async def __aenter__(self):
        await self.connect_db()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close_db()

    #### request functions

    async def _request(self, endpoint: str, headers: dict = None, params: dict = None, data: dict = None, json: dict = None) -> dict | Error_Balancer:
        result = await self._api_request_handler.request(
            endpoint=endpoint, method=HttpMethod.GET, headers=headers, params=params, data=data, json=json
        )
        if not isinstance(result, ErrorCode_Balancer):
            cprint(f"API 요청 성공: {endpoint}", 'green')

        return result

    async def _request_player(self, player_name: str) -> Player | Error_Balancer:
        player_data = await self._request(f'players?filter[playerNames]={player_name}')
        if isinstance(player_data, ErrorCode_Balancer):
            if player_data == ErrorCode_Balancer.PLAYER_NOT_FOUND:
                return PlayerNotFoundError_Balancer(message=f'{player_name} 플레이어를 찾을 수 없습니다. 플레이어 이름을 정확히 확인해주세요.')
            elif player_data == ErrorCode_Balancer.API_REQUEST_ERROR:
                return APIRequestError_Balancer(message=f'API 요청 중 에러가 발생하였습니다.')
            else:
                return Error_Balancer(message='API 요청 중 알 수 없는 에러가 발생하였습니다.')

        try:
            player = Player(
                id=player_data['data'][0]['id'],
                normalized_id=self._parse_player_id(player_data['data'][0]['id']),
                name=player_data['data'][0]['attributes']['name'],
                platform=player_data['data'][0]['attributes']['shardId'],
                ban_type=player_data['data'][0]['attributes']['banType'],
                clan_id=player_data['data'][0]['attributes']['clanId'],
                match_list=[match for match in player_data['data'][0]['relationships']['matches']['data'] if match['type'] == 'match'],
            )
            return player
        except IndexError as e:
            return IndexError_Balancer(message=e)
        except KeyError as e:
            return KeyError_Balancer(message=e)

    async def _request_seasons_data(self) -> str | Error_Balancer:
        season_data = await self._request('seasons')
        if isinstance(season_data, Error_Balancer):
            return season_data

        try:
            current_season = list(filter(lambda x: x['attributes']['isCurrentSeason'], season_data['data']))[0]
            return current_season
        except IndexError as e:
            return IndexError_Balancer(message=e)
        except KeyError as e:
            return KeyError_Balancer(message=e)

    async def _request_rank_stats(self, player_name: str, season_id: str) -> Stats | Error_Balancer:
        target_player = await self.find_player(player_name)
        player_rank_data = await self._request(f'players/{target_player.id}/seasons/{season_id}/ranked')
        if isinstance(player_rank_data, Error_Balancer):
            return player_rank_data

        try:
            squad_stats = player_rank_data['data']['attributes']['rankedGameModeStats']['squad']
            stats = Stats(
                type=MatchType.RANKED,
                tier=Tier.from_string(squad_stats['currentTier']['tier']),
                sub_tier=squad_stats['currentTier']['subTier'],
                rank_point=squad_stats['currentRankPoint'],
                rounds_played=squad_stats['roundsPlayed'],
                avg_rank=squad_stats['avgRank'],
                top10_ratio=squad_stats['top10Ratio'],
                win_ratio=squad_stats['winRatio'],
                damage_dealt=squad_stats['damageDealt'],
                kills=squad_stats['kills'],
                assists=squad_stats['assists'],
                deaths=squad_stats['deaths'],
                kda=squad_stats['kda'],
            )
        except IndexError as e:
            return IndexError_Balancer(message=e)
        except KeyError as e:
            return KeyError_Balancer(message=e)

        return stats

    async def _request_clan_data(self, clan_id: str = 'clan.fab1814f906d49b08d77b3adb783cc24') -> str:
        clan_data = await self._request(f'clans/{clan_id}')
        if isinstance(clan_data, Error_Balancer):
            return clan_data

        return clan_data

    async def _request_match(self, match_id: str) -> Match | Error_Balancer:
        match_data = await self._request(f'matches/{match_id}')
        if isinstance(match_data, Error_Balancer):
            return match_data

        try:
            match = Match(
                id=match_id,
                is_custom_match=match_data['data']['attributes']['isCustomMatch'],
                game_mode=GameMode.from_string(match_data['data']['attributes']['gameMode']),
                match_type=MatchType.from_string(match_data['data']['attributes']['matchType']),
                map_name=match_data['data']['attributes']['mapName'],
                duration=match_data['data']['attributes']['duration'],
                season_state=match_data['data']['attributes']['seasonState'],
                date=parse_utc_to_datetime(match_data['data']['attributes']['createdAt']),
                participants=list(filter(lambda x: x['type'] == 'participant', match_data['included'])),
            )
            return match
        except IndexError as e:
            return IndexError_Balancer(message=e)
        except KeyError as e:
            return KeyError_Balancer(message=e)

    async def _request_player_match_stats(self, player_name: str, match_id: str) -> PlayerMatchStats | Error_Balancer:
        target_player = await self.get_player(player_name, request_api=False)
        match = await self._request_match(match_id)
        if isinstance(target_player, PlayerNotFoundError_Balancer):
            return target_player
        if isinstance(match, PlayerMatchStatsNotFoundError_Balancer):
            return match

        return match.get_match_by_player_name(player_name)

    #### util functions

    def _parse_player_id(self, player_id: str) -> str:
        if 'account.' in player_id:
            return player_id.split('.')[1]
        elif '-' in player_id:
            return player_id.replace('-', '')

    def _calculate_stats_score(self, latest_player_match_stats_list: List[PlayerMatchStats]) -> float:
        total_score = 0
        A = -2.7557
        B = 13.2481
        C = 3.5403
        D = 1.4424
        E = 1.2

        for player_match_stats in latest_player_match_stats_list:
            match_type = player_match_stats.match_type
            if not match_type in [MatchType.NORMAL, MatchType.RANKED]:
                cprint(f"알 수 없는 매치 타입입니다. match_type: {match_type}", 'red')
                continue

            match_score = (
                (A + B * (1 / player_match_stats.win_place) + C * (player_match_stats.damage_dealt / 100) + D * player_match_stats.assists) * 1
                if match_type == MatchType.NORMAL
                else E
            )
            total_score += match_score

        return total_score / len(latest_player_match_stats_list)

    #### DB functions

    async def connect_db(self) -> None:
        if self._db_init:
            await self._db_handler.init()
        else:
            await self._db_handler.open()

    async def close_db(self) -> None:
        await self._db_handler.close()

    async def find_player(self, player_name: str) -> Player | Error_Balancer:
        return await self._db_handler.get_player(player_name=player_name)

    async def player_exist(self, player_name: str) -> bool | Error_Balancer:
        return await self._db_handler.is_player_exists(player_name=player_name)

    async def is_player_data_outdated(self, player_name: str, update_interval: timedelta = timedelta(days=7)) -> bool | Error_Balancer:
        return await self._db_handler.is_player_data_outdated(player_name=player_name, expiration_period=update_interval)

    async def update_player(self, player: Player) -> None:
        await self._db_handler.update_player(player=player)

    async def insert_player(self, player: Player) -> None:
        await self._db_handler.insert_player(player=player)

    # TODO: 아래 함수는 유저 밸런스 조정을 위해 사용자를 추가하기 위해 사용하는 것으로 변경해야함
    # def add_player(self, player_name: str) -> None:
    #     pass

    # def remove_player(self, player_name: str) -> None:
    #     pass

    #### public functions

    async def get_player(self, player_name: str, request_api: bool = False) -> Player | Error_Balancer:
        player = await self._request_player(player_name) if request_api else await self.find_player(player_name)
        if isinstance(player, Error_Balancer):
            return player

        if not await self.player_exist(player_name):
            await self.insert_player(player)
        if await self.is_player_data_outdated(player_name, update_interval=timedelta(hours=1)) == True:
            await self.update_player(player)

        return player

    async def get_player_match_stats(self, player_name: str, match_id: str) -> PlayerMatchStats | Error_Balancer:
        if await self._db_handler.is_player_match_stats_exists(player_name, match_id):
            player_match_stats = await self._db_handler.get_player_match_stats(player_name, match_id)
            return player_match_stats

        match = await self._request_match(match_id)
        if isinstance(match, Error_Balancer):
            return match

        player_match_stats = match.get_match_by_player_name(player_name)
        if isinstance(player_match_stats, PlayerMatchStatsNotFoundError_Balancer):
            return player_match_stats

        await self._db_handler.insert_player_match_stats(player_match_stats)
        return player_match_stats

    async def get_latest_player_match_stats_list(
        self, player_name: str, game_mode: GameMode = GameMode.SQUAD, max_match_num: int = 20
    ) -> List[PlayerMatchStats] | Error_Balancer:
        target_player = await self.get_player(player_name, request_api=False)
        if isinstance(target_player, PlayerNotFoundError_Balancer):
            return target_player

        # Get latest valid match player data
        latest_player_match_stats_list: List[PlayerMatchStats] = []
        match_count = 0
        for match_id in [match['id'] for match in target_player.match_list]:
            if match_count == max_match_num:
                break

            player_match_stats = await self.get_player_match_stats(player_name, match_id)
            if isinstance(player_match_stats, PlayerMatchStatsNotFoundError_Balancer):
                return player_match_stats
            if player_match_stats.game_mode != game_mode:
                continue
            if player_match_stats.match_type not in [MatchType.NORMAL, MatchType.RANKED]:
                continue

            latest_player_match_stats_list.append(player_match_stats)
            match_count += 1

        return latest_player_match_stats_list

    async def get_stats(self, player_name: str) -> Stats | Error_Balancer:
        target_player = await self.get_player(player_name, request_api=True)
        if isinstance(target_player, Error_Balancer):
            return target_player

        latest_player_match_stats_list: List[PlayerMatchStats] = await self.get_latest_player_match_stats_list(
            player_name, max_match_num=PUBG_Balancer.DEFAULT_MAX_MATCH_NUM
        )
        if isinstance(latest_player_match_stats_list, Error_Balancer):
            return latest_player_match_stats_list

        rounds_played = len(latest_player_match_stats_list)
        if rounds_played == 0:
            return PlayerMatchStatsNotFoundError_Balancer(message=f'{player_name} 플레이어의 최근 매치 정보를 가져오는 데 실패하였습니다.')
        elif rounds_played < int(PUBG_Balancer.DEFAULT_MAX_MATCH_NUM / 2):
            return PlayerMatchStatsNotEnoughError_Balancer(
                message=f'충분한 수의 최근 매치 정보가 부족합니다. 현재 진행된 매치 수: {rounds_played} / {int(PUBG_Balancer.DEFAULT_MAX_MATCH_NUM / 2)}'
            )

        stats_score = self._calculate_stats_score(latest_player_match_stats_list)
        kills = sum([match.kills for match in latest_player_match_stats_list])
        deaths = sum([1 if match.win_place != 1 else 0 for match in latest_player_match_stats_list])
        assists = sum([match.assists for match in latest_player_match_stats_list])
        kda = (kills + assists) / deaths if deaths else 0.0
        stats = Stats(
            rounds_played=rounds_played,
            avg_rank=sum([match.win_place for match in latest_player_match_stats_list]) / rounds_played,
            top10_ratio=sum([1 for match in latest_player_match_stats_list if match.win_place <= 10]) / rounds_played,
            win_ratio=sum([1 for match in latest_player_match_stats_list if match.win_place == 1]) / rounds_played,
            damage_dealt=sum([match.damage_dealt for match in latest_player_match_stats_list]),
            kills=kills,
            assists=deaths,
            deaths=assists,
            kda=kda,
            score=stats_score,
        )
        return stats


if __name__ == '__main__':

    async def main(player_name):
        async with PUBG_Balancer(api_key=os.environ['PUBG_TOKEN'], platform='steam', db_init=False) as pubg_balancer:
            stats = await pubg_balancer.get_stats(player_name)
            return stats

    player_name = 'Sodaman89'
    stats = asyncio.run(main(player_name))
    if not isinstance(stats, PlayerNotFoundError_Balancer):
        print(f'{player_name}\'s stats score: {stats.score}')
    else:
        print(stats)
