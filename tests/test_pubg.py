"""PUBG 밸런서 서비스 테스트. 실제 API 호출은 모두 대체한다."""

from __future__ import annotations

import pytest

from factories import MATCH_IDS, make_match_payload, make_player_payload
from ks_bot.common.enums import GameMode
from ks_bot.common.errors import NotEnoughMatchesError, PlayerMatchStatsNotFoundError, PlayerNotFoundError, ResourceNotFoundError
from ks_bot.core.pubg import PubgBalancer


class FakeApi:
    """엔드포인트별 응답을 미리 정해두는 가짜 API."""

    def __init__(self, responses: dict[str, dict] | None = None):
        self.responses = responses or {}
        self.calls: list[str] = []

    async def __call__(self, endpoint: str, params: dict | None = None) -> dict:
        self.calls.append(endpoint)
        if endpoint not in self.responses:
            raise ResourceNotFoundError(f'준비되지 않은 엔드포인트: {endpoint}')
        return self.responses[endpoint]


def build_api(player_name: str, *, match_count: int = 5, win_places: list[int] | None = None, game_mode: str = 'squad') -> FakeApi:
    win_places = win_places or [5] * match_count
    responses: dict[str, dict] = {
        f'players?filter[playerNames]={player_name}': {'data': [make_player_payload(player_name, match_count=match_count)]},
    }
    for match_id, win_place in zip(MATCH_IDS[:match_count], win_places, strict=False):
        responses[f'matches/{match_id}'] = make_match_payload(match_id, player_name, win_place=win_place, game_mode=game_mode)
    return FakeApi(responses)


@pytest.fixture
def player_name() -> str:
    return 'example_player_1'


class TestPlayerLookup:
    async def test_fetch_player_by_name(self, balancer: PubgBalancer, monkeypatch, player_name: str):
        monkeypatch.setattr(balancer, '_request', build_api(player_name))

        player = await balancer.fetch_player_by_name(player_name)
        assert player.name == player_name
        assert len(player.match_ids) == 5

    async def test_unknown_player_raises(self, balancer: PubgBalancer, monkeypatch):
        monkeypatch.setattr(balancer, '_request', FakeApi())
        with pytest.raises(PlayerNotFoundError):
            await balancer.fetch_player_by_name('없는사람')

    async def test_empty_data_raises(self, balancer: PubgBalancer, monkeypatch):
        monkeypatch.setattr(balancer, '_request', FakeApi({'players?filter[playerNames]=x': {'data': []}}))
        with pytest.raises(PlayerNotFoundError):
            await balancer.fetch_player_by_name('x')

    async def test_get_player_uses_cache_on_second_call(self, balancer: PubgBalancer, monkeypatch, player_name: str):
        api = build_api(player_name)
        monkeypatch.setattr(balancer, '_request', api)

        await balancer.get_player(player_name)
        await balancer.get_player(player_name)

        assert api.calls.count(f'players?filter[playerNames]={player_name}') == 1

    async def test_refresh_forces_api_call(self, balancer: PubgBalancer, monkeypatch, player_name: str):
        api = build_api(player_name)
        monkeypatch.setattr(balancer, '_request', api)

        await balancer.get_player(player_name)
        await balancer.get_player(player_name, refresh=True)

        assert api.calls.count(f'players?filter[playerNames]={player_name}') == 2

    async def test_sync_by_account_id_links_discord(self, balancer: PubgBalancer, monkeypatch, player_name: str):
        account_id = 'abc123'
        monkeypatch.setattr(balancer, '_request', FakeApi({f'players/{account_id}': {'data': make_player_payload(player_name)}}))

        player = await balancer.sync_player_by_account_id(account_id, discord_id=777)

        assert player.name == player_name
        assert await balancer.get_player_name_by_discord_id(777) == player_name


class TestMatchStats:
    async def test_match_stats_are_cached(self, balancer: PubgBalancer, monkeypatch, player_name: str):
        api = build_api(player_name)
        monkeypatch.setattr(balancer, '_request', api)
        match_id = MATCH_IDS[0]

        first = await balancer.get_player_match_stats(player_name, match_id)
        second = await balancer.get_player_match_stats(player_name, match_id)

        assert first == second
        assert api.calls.count(f'matches/{match_id}') == 1

    async def test_latest_stats_filter_by_game_mode(self, balancer: PubgBalancer, monkeypatch, player_name: str):
        api = build_api(player_name)
        monkeypatch.setattr(balancer, '_request', api)

        squad = await balancer.get_latest_player_match_stats_list(player_name, game_modes=[GameMode.SQUAD], max_match_num=10)
        solo = await balancer.get_latest_player_match_stats_list(player_name, game_modes=[GameMode.SOLO], max_match_num=10)

        assert len(squad) == 5
        assert solo == []

    async def test_fpp_squad_matches_are_included_by_default(self, balancer: PubgBalancer, monkeypatch, player_name: str):
        """예전에는 squad(TPP)만 인정해서 FPP 유저는 점수를 낼 수 없었다."""
        api = build_api(player_name, game_mode='squad-fpp')
        monkeypatch.setattr(balancer, '_request', api)

        collected = await balancer.get_latest_player_match_stats_list(player_name, max_match_num=10)

        assert len(collected) == 5
        assert all(stats.game_mode is GameMode.SQUAD_FPP for stats in collected)

    async def test_duo_matches_are_excluded_by_default(self, balancer: PubgBalancer, monkeypatch, player_name: str):
        monkeypatch.setattr(balancer, '_request', build_api(player_name, game_mode='duo-fpp'))

        assert await balancer.get_latest_player_match_stats_list(player_name, max_match_num=10) == []

    async def test_latest_stats_respect_limit(self, balancer: PubgBalancer, monkeypatch, player_name: str):
        monkeypatch.setattr(balancer, '_request', build_api(player_name))
        assert len(await balancer.get_latest_player_match_stats_list(player_name, max_match_num=2)) == 2

    async def test_unavailable_match_is_skipped(self, balancer: PubgBalancer, monkeypatch, player_name: str):
        api = build_api(player_name)
        del api.responses[f'matches/{MATCH_IDS[0]}']  # 조회 실패하는 매치
        monkeypatch.setattr(balancer, '_request', api)

        assert len(await balancer.get_latest_player_match_stats_list(player_name, max_match_num=10)) == 4


class TestGetStats:
    async def test_get_stats_aggregates(self, balancer: PubgBalancer, monkeypatch, player_name: str):
        monkeypatch.setattr(balancer, '_request', build_api(player_name, win_places=[1, 3, 8, 20, 40]))

        stats = await balancer.get_stats(player_name)

        # 픽스처의 max_match_num=4 이므로 최신 4경기만 집계한다.
        assert stats.rounds_played == 4
        assert stats.win_ratio == pytest.approx(1 / 4)
        assert stats.score != 0.0

    async def test_no_matches_raises(self, balancer: PubgBalancer, monkeypatch, player_name: str):
        api = build_api(player_name, match_count=0)
        monkeypatch.setattr(balancer, '_request', api)

        with pytest.raises(PlayerMatchStatsNotFoundError):
            await balancer.get_stats(player_name)

    async def test_not_enough_matches_raises(self, balancer: PubgBalancer, monkeypatch, player_name: str):
        # 픽스처의 max_match_num=4 이므로 필요한 최소 매치 수는 2다.
        monkeypatch.setattr(balancer, '_request', build_api(player_name, match_count=1))

        with pytest.raises(NotEnoughMatchesError) as exc_info:
            await balancer.get_stats(player_name)

        assert exc_info.value.required_match_num == 2
