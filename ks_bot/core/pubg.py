"""PUBG 밸런서 서비스.

PUBG API 호출과 로컬 캐시(SQLite)를 조합해, 코그(cog)가 쓰는 도메인 수준 API를 제공한다.
디스코드에 대한 의존성은 없다.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from types import TracebackType

from ks_bot.common.enums import GameMode, MatchType
from ks_bot.common.errors import (
    NotEnoughMatchesError,
    PlayerMatchStatsNotFoundError,
    PlayerNotFoundError,
    ResourceNotFoundError,
)
from ks_bot.common.models import Match, Player, PlayerMatchStats, Stats, normalize_player_id
from ks_bot.core.http_client import ApiClient, HttpMethod
from ks_bot.core.repository import PlayerRepository
from ks_bot.core.scoring import SCORABLE_MATCH_TYPES, aggregate_stats
from ks_bot.logging_config import get_logger

__all__ = ['DEFAULT_CLAN_ID', 'PubgBalancer']

logger = get_logger(__name__)

DEFAULT_CLAN_ID = 'clan.fab1814f906d49b08d77b3adb783cc24'


class PubgBalancer:
    """PUBG 전적 조회/점수 계산 서비스."""

    DEFAULT_MAX_MATCH_NUM = 40
    DEFAULT_DB_PATH = 'res/history.db'

    def __init__(
        self,
        api_key: str,
        platform: str = 'steam',
        *,
        db_path: str | Path = DEFAULT_DB_PATH,
        db_reset: bool = False,
        max_match_num: int = DEFAULT_MAX_MATCH_NUM,
        player_cache_ttl: timedelta = timedelta(hours=1),
    ):
        self._platform = platform
        self._max_match_num = max_match_num
        self._player_cache_ttl = player_cache_ttl
        self._db_reset = db_reset
        self._api = ApiClient(api_key=api_key, base_url=f'https://api.pubg.com/shards/{platform}')
        self._repo = PlayerRepository(db_path)

    @property
    def repository(self) -> PlayerRepository:
        return self._repo

    @property
    def max_match_num(self) -> int:
        return self._max_match_num

    @property
    def required_match_num(self) -> int:
        """점수 계산에 필요한 최소 매치 수."""
        return max(1, self._max_match_num // 2)

    # ---------- 수명 주기 ----------

    async def __aenter__(self) -> PubgBalancer:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def connect(self) -> PubgBalancer:
        await self._repo.connect(reset=self._db_reset)
        return self

    async def aclose(self) -> None:
        await self._repo.close()
        await self._api.aclose()

    # ---------- PUBG API ----------

    async def _request(self, endpoint: str, params: dict | None = None) -> dict:
        return await self._api.request(endpoint=endpoint, method=HttpMethod.GET, params=params)

    async def fetch_player_by_name(self, player_name: str) -> Player:
        """플레이어 이름으로 PUBG API를 조회한다."""
        try:
            payload = await self._request(f'players?filter[playerNames]={player_name}')
        except ResourceNotFoundError as e:
            raise PlayerNotFoundError(player_name=player_name) from e

        entries = payload.get('data') or []
        if not entries:
            raise PlayerNotFoundError(player_name=player_name)
        return Player.from_api(entries[0])

    async def fetch_player_by_account_id(self, account_id: str) -> Player:
        """PUBG 계정 ID로 플레이어를 조회한다."""
        try:
            payload = await self._request(f'players/{account_id}')
        except ResourceNotFoundError as e:
            raise PlayerNotFoundError(player_name=account_id) from e

        data = payload.get('data')
        if not data:
            raise PlayerNotFoundError(player_name=account_id)
        return Player.from_api(data)

    async def fetch_current_season(self) -> dict:
        payload = await self._request('seasons')
        seasons = [season for season in payload.get('data', []) if season.get('attributes', {}).get('isCurrentSeason')]
        if not seasons:
            raise ResourceNotFoundError('현재 시즌 정보를 찾을 수 없습니다.')
        return seasons[0]

    async def fetch_ranked_stats(self, player_name: str, season_id: str) -> Stats:
        player = await self.get_player(player_name)
        payload = await self._request(f'players/{player.id}/seasons/{season_id}/ranked')
        squad_stats = payload.get('data', {}).get('attributes', {}).get('rankedGameModeStats', {}).get('squad')
        if not squad_stats:
            raise PlayerMatchStatsNotFoundError(player_name=player_name)
        return Stats.from_ranked_api(squad_stats)

    async def fetch_clan(self, clan_id: str = DEFAULT_CLAN_ID) -> dict:
        return await self._request(f'clans/{clan_id}')

    async def fetch_match(self, match_id: str) -> Match:
        payload = await self._request(f'matches/{match_id}')
        return Match.from_api(match_id, payload)

    # ---------- 저장소 위임 ----------

    async def is_player_exist(self, player_name: str) -> bool:
        return await self._repo.player_exists(player_name=player_name)

    async def link_discord_account(self, player_name: str, discord_id: int | None) -> None:
        await self._repo.set_discord_id(player_name=player_name, discord_id=discord_id)

    async def get_player_name_by_discord_id(self, discord_id: int) -> str:
        return await self._repo.get_player_name_by_discord_id(discord_id=discord_id)

    # ---------- 도메인 기능 ----------

    async def get_player(self, player_name: str, *, refresh: bool = False) -> Player:
        """플레이어 정보를 얻는다.

        캐시가 있고 만료되지 않았다면 DB 값을 쓰고, 아니면 PUBG API에서 새로 받아 저장한다.
        """
        if not refresh and await self._repo.player_exists(player_name=player_name):
            outdated = await self._repo.is_player_data_outdated(player_name=player_name, expiration_period=self._player_cache_ttl)
            if not outdated:
                return await self._repo.get_player(player_name=player_name)

        player = await self.fetch_player_by_name(player_name)
        await self._repo.upsert_player(player)
        return player

    async def sync_player_by_account_id(self, account_id: str, discord_id: int | None = None) -> Player:
        """PUBG 계정 ID로 최신 정보를 받아 DB에 반영하고, 필요하면 디스코드 계정을 연결한다."""
        player = await self.fetch_player_by_account_id(normalize_player_id(account_id) or account_id)
        await self._repo.upsert_player(player)
        if discord_id is not None:
            await self._repo.set_discord_id(player_name=player.name, discord_id=discord_id)
        return player

    async def get_player_match_stats(self, player_name: str, match_id: str) -> PlayerMatchStats:
        """단일 매치 전적을 얻는다(캐시 우선)."""
        if await self._repo.player_match_stats_exists(player_name, match_id):
            return await self._repo.get_player_match_stats(player_name, match_id)

        match = await self.fetch_match(match_id)
        stats = match.player_stats(player_name)
        await self._repo.upsert_player_match_stats(stats)
        return stats

    async def get_latest_player_match_stats_list(
        self,
        player_name: str,
        game_mode: GameMode = GameMode.SQUAD,
        max_match_num: int | None = None,
    ) -> list[PlayerMatchStats]:
        """최근 매치 중 조건에 맞는 전적을 최대 `max_match_num`건 모은다."""
        limit = max_match_num or self._max_match_num
        player = await self.get_player(player_name)
        cached = await self._repo.get_player_match_stats_bulk(player_name, player.match_ids)

        collected: list[PlayerMatchStats] = []
        for match_id in player.match_ids:
            if len(collected) >= limit:
                break

            stats = cached.get(match_id)
            if stats is None:
                try:
                    match = await self.fetch_match(match_id)
                    stats = match.player_stats(player_name)
                    await self._repo.upsert_player_match_stats(stats)
                except (PlayerMatchStatsNotFoundError, ResourceNotFoundError) as e:
                    logger.debug('매치 전적을 건너뜁니다. match_id=%s, 사유=%s', match_id, e)
                    continue

            if stats.game_mode != game_mode:
                continue
            if stats.match_type not in SCORABLE_MATCH_TYPES:
                continue

            collected.append(stats)

        return collected

    async def get_stats(self, player_name: str) -> Stats:
        """플레이어의 최근 전적을 집계한 스탯을 반환한다.

        Raises:
            PlayerNotFoundError: 플레이어를 찾을 수 없는 경우.
            PlayerMatchStatsNotFoundError: 최근 매치 전적이 하나도 없는 경우.
            NotEnoughMatchesError: 점수를 내기에 매치 수가 부족한 경우.
        """
        matches = await self.get_latest_player_match_stats_list(player_name, max_match_num=self._max_match_num)

        if not matches:
            raise PlayerMatchStatsNotFoundError(player_name=player_name)
        if len(matches) < self.required_match_num:
            raise NotEnoughMatchesError(match_num=len(matches), required_match_num=self.required_match_num)

        stats = aggregate_stats(matches)
        stats.type = MatchType.NORMAL
        return stats
