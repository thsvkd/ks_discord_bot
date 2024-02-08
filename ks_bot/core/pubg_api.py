import os
from termcolor import colored, cprint
from typing import List, Dict, Union
from ks_bot.core.request_handler import HttpMethod, APIRequestHandler
from ks_bot.common.error import ErrorCode_Balancer
from ks_bot.common.enum import GameMode, MatchType, Tier
from ks_bot.common.dataclass import Player, Match, Stats, PlayerMatchStats


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

    def get_stats_score(self, player_name: str) -> Union[float, ErrorCode_Balancer]:
        target_player = self.find_player(player_name)

        if target_player.is_updated:
            return target_player.stats_score
        else:
            result = self.update_player_data(player_name)
            if result == ErrorCode_Balancer.NO_ERROR:
                return target_player.stats_score
            else:
                return result

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
                match_score *= 1.2
            elif match_type == MatchType.NORMAL:
                match_score *= 1
            else:
                cprint(f"알 수 없는 매치 타입입니다. match_type: {match_type}", 'red')

            total_score += match_score

        return total_score / len(latest_matches)

    def update_player_data(self, player_name: str, game_mode: GameMode = GameMode.SQUAD, max_match_num: int = 20) -> ErrorCode_Balancer:
        target_player = self.find_player(player_name)

        if target_player.is_updated:
            return ErrorCode_Balancer.ALREADY_UPDATED

        # Get basic player data
        player_data = self._request(f'players?filter[playerNames]={player_name}')

        if player_data is None:
            cprint(f"{player_name} 플레이어 데이터를 가져오는 데 실패하였습니다. 플레이어 이름의 철자를 확인해주세요.", 'red')
            return ErrorCode_Balancer.PLAYER_NOT_FOUND

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

        target_player.is_updated = True
        return ErrorCode_Balancer.NO_ERROR

    def update_all_player_data(self, game_mode: GameMode = GameMode.SQUAD, max_match_num: int = 20) -> None:
        for player in self._players:
            cprint(f'{player.name} 플레이어 업데이트 시작', 'cyan', end='')
            result = self.update_player_data(player_name=player.name, game_mode=game_mode, max_match_num=max_match_num)
            if result == ErrorCode_Balancer.NO_ERROR:
                cprint(f'\r{player.name} 플레이어 업데이트 완료. (stats_score: {player.stats_score})', 'green')
            elif result == ErrorCode_Balancer.PLAYER_NOT_FOUND:
                cprint(f'\r{player.name} 플레이어 업데이트 실패. (플레이어 이름을 정확히 입력해주세요.)', 'red')
            else:
                cprint(f'\r{player.name} 플레이어 업데이트 실패. (알 수 없는 오류, result: {result})', 'red')

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
