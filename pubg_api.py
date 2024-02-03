import requests
from dataclasses import dataclass
from typing import List, Dict, Union


API_KEY = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJqdGkiOiIzYTcyNDIxMC0wYzE5LTAxM2EtZGI0YS0wMDdjMDliNGQ1NzkiLCJpc3MiOiJnYW1lbG9ja2VyIiwiaWF0IjoxNjMzODg1MTE0LCJwdWIiOiJibHVlaG9sZSIsInRpdGxlIjoicHViZyIsImFwcCI6ImJhdHRsZXNraWxsIn0.2e9QTTGN1oYROSz2SeBq-AyL_ZdSMmUlTUQaCInRnCQ'  # 여기에 발급받은 API 키를 입력하세요.


@dataclass
class Player:
    id: str
    name: str
    stats: dict


@dataclass
class Match:
    id: str
    participants: list

    def get_player_match_status(self, player_name: str) -> Union[Dict, None]:
        for participant in self.participants:
            participant_name = participant['attributes']['stats']['name']
            if participant_name == player_name:
                return participant['attributes']['stats']


class PUBG_Balancer:
    def __init__(self, api_key: str, region: str = 'steam'):
        self._api_key = api_key
        self._region = region
        self._header = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/vnd.api+json"}

        self._players: List[Player] = []

    def _find_player(self, name: str) -> Union[Player, None]:
        for player in self._players:
            if player.name == name:
                return player
        return None

    def add_player(self, name: str) -> None:
        player_match_info = self.get_player_data(name)
        player = Player(*player_match_info)
        self._players.append(player)

    def remove_player(self, name: str) -> None:
        self._players.remove(name)

    def get_player_data(self, name: str) -> Dict:
        url = f"https://api.pubg.com/shards/{self._region}/players?filter[playerNames]={name}"
        response = requests.get(url, headers=self._header)
        player_data = response.json()

        try:
            player_id = player_data['data'][0]['id']
            player_name = player_data['data'][0]['attributes']['stats']['name']
            matches = player_data['data'][0]['relationships']['matches']['data']
            return player_id, player_name, matches
        except IndexError:
            return None


try:
    player_id = player_data['data'][0]['id']

    # 플레이어의 최근 매치 조회
    matches = player_data['data'][0]['relationships']['matches']['data']
    print(f"{PLAYER_NAME}의 최근 매치 정보:")

    # 최근 20개의 매치 정보만 출력
    for match in matches[:20]:
        print(match['id'])
        response = requests.get(f"https://api.pubg.com/shards/steam/matches/{match['id']}", headers=HEADER)
        match_data = response.json()
        match = Match(match['id'], match_data['included'])
        player_match_info = match.get_player_match_status(PLAYER_NAME)
except IndexError:
    print("플레이어 정보를 찾을 수 없습니다.")

if __name__ == '__main__':
    PLAYER_NAME = 'SonPANG'  # 조회하려는 플레이어 이름
    pubg_balancer = PUBG_Balancer(api_key=API_KEY, region='steam')
