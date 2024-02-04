import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import os
from termcolor import colored, cprint
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Union
import json
import time
from enum import Enum, auto


def print_dict_pretty(json_data: Union[Dict, List]) -> None:
    print(json.dumps(json_data, indent=4, ensure_ascii=False))


class GameMode(Enum):
    UNDEFINED = auto()
    DUO = 'duo'
    DUO_FPP = 'duo-fpp'
    SOLO = 'solo'
    SOLO_FPP = 'solo-fpp'
    SQUAD = 'squad'
    SQUAD_FPP = 'squad-fpp'
    CONQUEST_DUO = 'conquest-duo'
    CONQUEST_DUO_FPP = 'conquest-duo-fpp'
    CONQUEST_SOLO = 'conquest-solo'
    CONQUEST_SOLO_FPP = 'conquest-solo-fpp'
    CONQUEST_SQUAD = 'conquest-squad'
    CONQUEST_SQUAD_FPP = 'conquest-squad-fpp'
    ESPORTS_DUO = 'esports-duo'
    ESPORTS_DUO_FPP = 'esports-duo-fpp'
    ESPORTS_SOLO = 'esports-solo'
    ESPORTS_SOLO_FPP = 'esports-solo-fpp'
    ESPORTS_SQUAD = 'esports-squad'
    ESPORTS_SQUAD_FPP = 'esports-squad-fpp'
    LAB_TPP = 'lab-tpp'
    LAB_FPP = 'lab-fpp'
    NORMAL_DUO = 'normal-duo'
    NORMAL_DUO_FPP = 'normal-duo-fpp'
    NORMAL_SOLO = 'normal-solo'
    NORMAL_SOLO_FPP = 'normal-solo-fpp'
    NORMAL_SQUAD = 'normal-squad'
    NORMAL_SQUAD_FPP = 'normal-squad-fpp'
    TDM = 'tdm'
    WAR_DUO = 'war-duo'
    WAR_DUO_FPP = 'war-duo-fpp'
    WAR_SOLO = 'war-solo'
    WAR_SOLO_FPP = 'war-solo-fpp'
    WAR_SQUAD = 'war-squad'
    WAR_SQUAD_FPP = 'war-squad-fpp'
    ZOMBIE_DUO = 'zombie-duo'
    ZOMBIE_DUO_FPP = 'zombie-duo-fpp'
    ZOMBIE_SOLO = 'zombie-solo'
    ZOMBIE_SOLO_FPP = 'zombie-solo-fpp'
    ZOMBIE_SQUAD = 'zombie-squad'
    ZOMBIE_SQUAD_FPP = 'zombie-squad-fpp'

    @classmethod
    def from_string(cls, value: str):
        for member in cls:
            if member.value == value:
                return member
        return cls.UNDEFINED


class MatchType(Enum):
    UNDEFINED = auto()
    AIROYALE = 'airoyale'
    ARCADE = 'arcade'
    CUSTOM = 'custom'
    EVENT = 'event'
    SEASONAL = 'seasonal'
    TRAINING = 'training'
    NORMAL = 'official'
    RANKED = 'competitive'

    @classmethod
    def from_string(cls, value: str):
        for member in cls:
            if member.value == value:
                return member
        return cls.UNDEFINED


class Tier(Enum):
    UNDEFINED = auto()
    BRONZE = 'bronze'
    SILVER = 'silver'
    GOLD = 'gold'
    PLATINUM = 'platinum'
    DIAMOND = 'diamond'
    MASTER = 'master'

    @classmethod
    def from_string(cls, value: str):
        for member in cls:
            if member.value == value:
                return member
        return cls.UNDEFINED


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
    is_update: bool = False
    latest_matches_info: list = field(default_factory=list)
    latest_matches: List[Match] = field(default_factory=list)
    platform: str = ''
    ban_type: str = ''
    clan_id: str = ''
    rank_stats: dict = field(default_factory=dict)
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


class HttpMethod(Enum):
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    DELETE = 'DELETE'
    PATCH = 'PATCH'


import time


class APIRequestHandler:
    def __init__(self, api_key: str, base_url: str, max_retries: int = 3, timeout: float = 5.0, rate_limit_per_minute: int = 10):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.timeout = timeout
        self.rate_limit_per_minute = rate_limit_per_minute
        self.remaining_requests = rate_limit_per_minute
        self.rate_limit_reset_timestamp = time.time()
        retries = Retry(total=max_retries, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    def wait_for_rate_limit_reset(self):
        current_time = time.time()
        while self.remaining_requests <= 0 and current_time < self.rate_limit_reset_timestamp:
            sleep_time = self.rate_limit_reset_timestamp - current_time
            cprint(f"\rRate limit exceeded. Waiting for {sleep_time:.0f} seconds.", 'yellow', end='')
            time.sleep(1)
            current_time = time.time()
        else:
            print("\nRate limit has been reset. Continuing with the requests.")

    def request(
        self, endpoint: str, method: HttpMethod = HttpMethod.GET, headers: dict = None, params: dict = None, data: dict = None, json: dict = None
    ) -> dict:
        url = f'{self.base_url}/{endpoint}'
        default_headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/vnd.api+json"}
        if headers:
            default_headers.update(headers)

        try:
            response = self.session.request(method.value, url, headers=default_headers, params=params, json=json, data=data, timeout=self.timeout)
            if response.status_code == 429:
                # We've hit the rate limit, set remaining requests to 0 and calculate reset time
                self.remaining_requests = 0
                self.rate_limit_reset_timestamp = float(response.headers.get('X-RateLimit-Reset', time.time()))
                self.wait_for_rate_limit_reset()
                return self.request(endpoint, method, headers, params, data, json)  # Retry the request
            response.raise_for_status()
            # Update remaining requests from headers
            self.remaining_requests = int(response.headers.get('X-RateLimit-Remaining', self.remaining_requests))
            self.rate_limit_reset_timestamp = float(response.headers.get('X-RateLimit-Reset', self.rate_limit_reset_timestamp))
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
        except requests.exceptions.ConnectionError as conn_err:
            print(f"Connection error occurred: {conn_err}")
        except requests.exceptions.Timeout as timeout_err:
            print(f"Timeout error occurred: {timeout_err}")
        except requests.exceptions.RequestException as err:
            print(f"An error occurred: {err}")
        return None


class PUBG_Balancer:
    def __init__(self, api_key: str, platform: str = 'steam'):
        self._api_key = api_key
        self._platform = platform
        self._header = {"Authorization": f"Bearer {self._api_key}", "Accept": "application/vnd.api+json"}
        self._base_url = f'https://api.pubg.com/shards/{self._platform}'
        self._api_request_handler = APIRequestHandler(api_key=self._api_key, base_url=self._base_url)

        self._players: List[Player] = []

    def _request(self, endpoint: str, headers: dict = None, params: dict = None, data: dict = None, json: dict = None) -> dict:
        return self._api_request_handler.request(endpoint=endpoint, method=HttpMethod.GET, headers=headers, params=params, data=data, json=json)

    def parse_player_id(self, player_id: str) -> str:
        if 'account.' in player_id:
            return player_id.split('.')[1]
        elif '-' in player_id:
            return player_id.replace('-', '')

    def find_player(self, player_name: str) -> Player:
        for player in self._players:
            if player.name == player_name:
                return player
        else:
            return Player()

    def is_player_exist(self, player_name: str) -> bool:
        return bool(self.find_player(player_name).name)

    def add_player(self, player_name: str) -> None:
        if self.find_player(player_name).name:
            cprint(f"{player_name} 플레이어는 이미 추가되어 있습니다.", 'yellow')

        player = Player(name=player_name)
        self._players.append(player)

    def remove_player(self, player_name: str) -> None:
        target_player = self.find_player(player_name)
        self._players.remove(target_player)

    def get_seasons_data(self) -> str:
        season_data = self._request('seasons')
        current_season = list(filter(lambda x: x['attributes']['isCurrentSeason'], season_data['data']))[0]
        return current_season

    def get_clan_data(self, clan_id: str = 'clan.fab1814f906d49b08d77b3adb783cc24') -> str:
        clan_data = self._request(f'clans/{clan_id}')
        return clan_data

    def get_match(self, match_id: str) -> Match:
        match_data = self._request(f'matches/{match_id}')

        match = Match(
            id=match_id,
            is_custom_match=match_data['data']['attributes']['isCustomMatch'],
            game_mode=GameMode.from_string(match_data['data']['attributes']['gameMode']),
            match_type=MatchType.from_string(match_data['data']['attributes']['matchType']),
            participants=list(filter(lambda x: x['type'] == 'participant', match_data['included'])),
        )

        return match

    def get_rank_stats(self, player_name: str, season_id: str) -> Stats:
        target_player = self.find_player(player_name)

        player_rank_data = self._request(f'players/{target_player.id}/seasons/{season_id}/ranked')
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

        return stats

    def get_stats_score(self, player_name: str) -> float:
        target_player = self.find_player(player_name)

        if target_player.is_update:
            return target_player.stats_score
        else:
            self.update_player_data(player_name)
            return target_player.stats_score

    def calculate_stats_score(self, player_name: str, latest_matches: List[Match]) -> float:
        total_score = 0

        for match in latest_matches:
            player_stats_info = match.find_player_stats_info(player_name)
            match_type = match.match_type
            player_match_stats = PlayerMatchStats(
                player_name=player_name,
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

            # 공식 1번안
            # match_score = -2.7557 + 13.2481 * (1 / player_match_stats.win_place) + 3.5403 * player_match_stats.kills + 1.4424 * player_match_stats.assists
            # 공식 2번안
            match_score = (
                -2.7557
                + 13.2481 * (1 / player_match_stats.win_place)
                + 3.5403 * (player_match_stats.damage_dealt / 100)
                + 1.4424 * player_match_stats.assists
            )
            if match_type == MatchType.RANKED:
                match_score *= 2
            elif match_type == MatchType.NORMAL:
                match_score *= 1
            else:
                cprint(f"알 수 없는 매치 타입입니다. match_type: {match_type}", 'red')

            total_score += match_score

        return total_score / len(latest_matches)

    def update_player_data(self, player_name: str, game_mode: GameMode = GameMode.SQUAD, max_match_num: int = 20) -> None:
        target_player = self.find_player(player_name)

        if target_player.is_update:
            return None

        # Get basic player data
        player_data = self._request(f'players?filter[playerNames]={player_name}')

        try:
            target_player.id = player_data['data'][0]['id']
            target_player.normalized_id = self.parse_player_id(player_data['data'][0]['id'])
            target_player.name = player_data['data'][0]['attributes']['name']
            target_player.platform = player_data['data'][0]['attributes']['shardId']
            target_player.ban_type = player_data['data'][0]['attributes']['banType']
            target_player.clan_id = player_data['data'][0]['attributes']['clanId']
        except IndexError as e:
            cprint(e, 'red')

        # Get rank match player data
        # current_season = self.get_seasons_data()
        # season_id = current_season['id']
        # rank_stats = self.get_rank_stats(player_name, season_id)
        # target_player.rank_stats = rank_stats

        # Get normal match player data
        try:
            latest_matches_info = player_data['data'][0]['relationships']['matches']['data']
            latest_matches: List[Match] = []

            # Get latest valid matched
            count = 0
            for match_info in latest_matches_info:
                if count == max_match_num:
                    break

                match = self.get_match(match_info['id'])
                if not (
                    match.game_mode == game_mode
                    and match.match_type in [MatchType.NORMAL, MatchType.RANKED]
                    and match.find_player_stats_info(player_name)
                ):
                    continue

                latest_matches.append(match)
                count += 1
            else:
                cprint(
                    f"{max_match_num}개 만큼의 유효한 최근 매치 정보를 가져오는 데 실패하였습니다. player: {player_name}, match_num: {count}",
                    'yellow',
                )

            target_player.stats_score = self.calculate_stats_score(player_name, latest_matches)
        except IndexError as e:
            cprint(e, 'red')

        target_player.is_update = True

    def update_all_player_data(self, game_mode: GameMode = GameMode.SQUAD, max_match_num: int = 20) -> None:
        for player in self._players:
            cprint(f'{player.name} 플레이어 업데이트 시작', 'cyan', end='')
            self.update_player_data(player_name=player.name, game_mode=game_mode, max_match_num=max_match_num)
            cprint(f'\r{player.name} 플레이어 업데이트 완료. (stats_score: {player.stats_score})', 'green')

    def export_score_data(self) -> Dict:
        self.update_all_player_data()

        with open('player_data.txt', 'w', encoding='UTF-8') as f:
            player_data = [f'{player.name:<}, {player.stats_score:> .04f}\n' for player in self._players]
            f.writelines(player_data)


def main():
    pubg_balancer = PUBG_Balancer(api_key=os.environ['PUBG_TOKEN'], platform='steam')
    with open('clan_mambers.txt', 'r', encoding='UTF-8') as f:
        player_data = f.readlines()
        for line in player_data:
            pubg_balancer.add_player(line.strip())

    # pubg_balancer.add_player('SonPANG')
    # pubg_balancer.add_player('Sodaman89')
    # pubg_balancer.add_player('DefSomeone')
    # pubg_balancer.add_player('POSTINO-1')
    # pubg_balancer.add_player('gpfskdlxm')
    # pubg_balancer.add_player('SonHeungMin7')
    # pubg_balancer.add_player('PUMP_______JUNI')
    # pubg_balancer.add_player('Hyun_Rang')
    # pubg_balancer.add_player('VSS_Fighter')
    # pubg_balancer.add_player('ChicMoon')
    # pubg_balancer.add_player('NeedbxckTereA')
    # pubg_balancer.add_player('Sunhyeolru')

    pubg_balancer.export_score_data()
    # pubg_balancer.update_all_player_data(max_match_num=20)


if __name__ == '__main__':
    main()

    # pubg_balancer = PUBG_Balancer(api_key=os.environ['PUBG_TOKEN'], platform='steam')
    # player_name = 'SonPANG'
    # pubg_balancer.add_player(player_name)
    # pubg_balancer.update_player_data(player_name)
    # print(f'{player_name}\'s stats score: {pubg_balancer.get_stats_score(player_name)}')
