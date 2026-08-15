"""무료 배포 수집 서비스 테스트. 실제 HTTP 호출은 모두 대체한다."""

from __future__ import annotations

from typing import Any

import pytest

from ks_bot.common.errors import ApiRequestError
from ks_bot.common.giveaway import ClaimKind, Store
from ks_bot.core.giveaway import (
    EPIC_ENDPOINT,
    GAMERPOWER_ENDPOINT,
    STEAM_APPDETAILS_ENDPOINT,
    GiveawayService,
)

# GamerPower 중계 링크 → 실제 스토어 주소. 브라우저 헤더를 붙이면 이렇게 리다이렉트된다.
REDIRECTS = {
    'https://www.gamerpower.com/open/deponia-steam-giveaway': 'https://store.steampowered.com/app/214340/Deponia/',
    'https://www.gamerpower.com/open/dwarven-realms-steam-key-giveaway': 'https://store.steampowered.com/app/2015240/Dwarven_Realms/',
    'https://www.gamerpower.com/open/caravan-sandwitch-epic-games-giveaway': 'https://store.epicgames.com/p/caravan-sandwitch-05ff58',
}


class FakeHttp:
    """엔드포인트별 응답과 리다이렉트를 미리 정해두는 가짜 클라이언트."""

    def __init__(self, responses: dict[str, Any], redirects: dict[str, str] | None = None):
        self.responses = responses
        self.redirects = redirects or {}
        self.requests: list[tuple[str, dict]] = []
        self.resolved: list[str] = []

    async def request(self, endpoint: str, params: dict | None = None) -> Any:
        self.requests.append((endpoint, params or {}))
        if endpoint not in self.responses:
            raise ApiRequestError(f'준비되지 않은 엔드포인트: {endpoint}')

        payload = self.responses[endpoint]
        if endpoint == STEAM_APPDETAILS_ENDPOINT:
            appid = str((params or {}).get('appids', ''))
            return {appid: payload.get(appid, {'success': False})}
        return payload

    async def resolve_final_url(self, url: str, header: dict | None = None) -> str:
        self.resolved.append(url)
        if url not in self.redirects:
            raise ApiRequestError(f'해석할 수 없는 링크: {url}')
        return self.redirects[url]


def install(service: GiveawayService, http: FakeHttp, monkeypatch: pytest.MonkeyPatch) -> FakeHttp:
    monkeypatch.setattr(service, '_request', http.request)
    monkeypatch.setattr(service._client, 'resolve_final_url', http.resolve_final_url)
    return http


@pytest.fixture
def http(epic_payload: dict, gamerpower_payload: list[dict], steam_appdetails: dict) -> FakeHttp:
    return FakeHttp(
        {
            EPIC_ENDPOINT: epic_payload,
            GAMERPOWER_ENDPOINT: gamerpower_payload,
            STEAM_APPDETAILS_ENDPOINT: steam_appdetails,
        },
        REDIRECTS,
    )


class TestCollect:
    async def test_epic_and_gamerpower_are_merged(self, giveaway_service: GiveawayService, http: FakeHttp, monkeypatch, frozen_now):
        """Caravan SandWitch는 두 수집처에 모두 있다. 한 건으로 합쳐져야 한다."""
        install(giveaway_service, http, monkeypatch)
        giveaway_service.stores = frozenset({Store.EPIC})

        collected = await giveaway_service.collect()

        caravan = [item for item in collected if 'Caravan' in item.title]
        assert len(caravan) == 1
        assert caravan[0].source == 'epic'
        # Epic에 없던 값은 GamerPower에서 채워진다.
        assert caravan[0].url == 'https://store.epicgames.com/p/caravan-sandwitch-05ff58'

    async def test_store_whitelist_is_applied(self, giveaway_service: GiveawayService, http: FakeHttp, monkeypatch, frozen_now):
        install(giveaway_service, http, monkeypatch)
        giveaway_service.stores = frozenset({Store.STEAM})

        collected = await giveaway_service.collect()

        assert collected
        assert {item.store for item in collected} == {Store.STEAM}

    async def test_itch_is_excluded_by_default_config(self, giveaway_service: GiveawayService, http: FakeHttp, monkeypatch, frozen_now):
        install(giveaway_service, http, monkeypatch)
        giveaway_service.stores = frozenset({Store.STEAM, Store.EPIC, Store.GOG})

        assert Store.ITCH not in {item.store for item in await giveaway_service.collect()}

    async def test_upcoming_can_be_turned_off(self, giveaway_service: GiveawayService, http: FakeHttp, monkeypatch, frozen_now):
        install(giveaway_service, http, monkeypatch)
        giveaway_service.stores = frozenset({Store.EPIC})
        giveaway_service.include_upcoming = False

        assert all(not item.is_upcoming for item in await giveaway_service.collect())

    async def test_one_failing_source_does_not_break_the_rest(self, giveaway_service: GiveawayService, monkeypatch, frozen_now, gamerpower_payload):
        install(giveaway_service, FakeHttp({GAMERPOWER_ENDPOINT: gamerpower_payload}, REDIRECTS), monkeypatch)
        giveaway_service.stores = frozenset({Store.STEAM})

        collected = await giveaway_service.collect()

        assert [item.title for item in collected] == ['Deponia', 'Dwarven Realms']

    async def test_all_sources_failing_yields_nothing(self, giveaway_service: GiveawayService, monkeypatch, frozen_now):
        install(giveaway_service, FakeHttp({}), monkeypatch)
        assert await giveaway_service.collect() == []


class TestUrlResolution:
    async def test_redirect_becomes_the_product_identity(self, giveaway_service: GiveawayService, http: FakeHttp, monkeypatch, frozen_now):
        install(giveaway_service, http, monkeypatch)
        giveaway_service.stores = frozenset({Store.STEAM})

        deponia = next(item for item in await giveaway_service.collect() if item.title == 'Deponia')

        assert deponia.url == 'https://store.steampowered.com/app/214340/Deponia/'
        assert deponia.key == 'steam:214340'
        assert deponia.extra_urls == ('https://www.gamerpower.com/open/deponia-steam-giveaway',)

    async def test_resolution_is_cached_across_polls(self, giveaway_service: GiveawayService, http: FakeHttp, monkeypatch, frozen_now):
        """중계 링크 해석은 네트워크 요청이라, 폴링마다 반복하면 비용이 그대로 늘어난다."""
        install(giveaway_service, http, monkeypatch)
        giveaway_service.stores = frozenset({Store.STEAM})

        await giveaway_service.collect()
        first_round = len(http.resolved)
        await giveaway_service.collect()

        assert first_round > 0
        assert len(http.resolved) == first_round

    async def test_failed_resolution_is_not_retried_every_poll(self, giveaway_service: GiveawayService, http: FakeHttp, monkeypatch, frozen_now):
        """끝내 해석되지 않는 링크를 30분마다 다시 두드리면 요청만 낭비된다."""
        install(giveaway_service, http, monkeypatch)
        giveaway_service.stores = None  # 모든 스토어를 대상으로 삼아 해석 실패를 유도한다.

        await giveaway_service.collect()
        first_round = len(http.resolved)
        await giveaway_service.collect()

        assert first_round > len(REDIRECTS)  # 해석에 실패한 링크가 실제로 있었다.
        assert len(http.resolved) == first_round

    async def test_out_of_scope_stores_are_never_resolved(self, giveaway_service: GiveawayService, http: FakeHttp, monkeypatch, frozen_now):
        """대상이 아닌 스토어는 중계 링크를 열어볼 필요가 없다."""
        install(giveaway_service, http, monkeypatch)
        giveaway_service.stores = frozenset({Store.STEAM})

        await giveaway_service.collect()

        assert all('itch' not in url for url in http.resolved)

    async def test_unresolvable_link_keeps_the_original(self, giveaway_service: GiveawayService, monkeypatch, frozen_now):
        payload = [
            {
                'id': 99,
                'title': 'Mystery (Steam) Giveaway',
                'type': 'Game',
                'status': 'Active',
                'platforms': 'PC, Steam',
                'open_giveaway_url': 'https://www.gamerpower.com/open/mystery',
            }
        ]
        install(giveaway_service, FakeHttp({GAMERPOWER_ENDPOINT: payload}), monkeypatch)
        giveaway_service.stores = frozenset({Store.STEAM})

        collected = await giveaway_service.collect()

        assert len(collected) == 1
        assert collected[0].url == 'https://www.gamerpower.com/open/mystery'


class TestSteamEnrichment:
    async def test_korean_metadata_is_filled_in(self, giveaway_service: GiveawayService, http: FakeHttp, monkeypatch, frozen_now):
        """LLM 없이도 한국어 설명·장르·가격·평점이 모두 채워진다."""
        install(giveaway_service, http, monkeypatch)
        giveaway_service.stores = frozenset({Store.STEAM})

        deponia = next(item for item in await giveaway_service.find_new() if item.title == 'Deponia')

        assert deponia.genres == ('어드벤처', '인디')
        assert '데포니아' in deponia.description
        assert deponia.original_price == '₩ 10,500'
        assert deponia.metacritic == 74
        assert deponia.thumbnail_url.startswith('https://')

    async def test_store_free_claim_is_verified_against_steam(self, giveaway_service: GiveawayService, monkeypatch, frozen_now, steam_appdetails):
        """수집처가 '무료'라고 해도 스토어에서 실제로 무료가 아니면 발행하지 않는다."""
        payload = [
            {
                'id': 1,
                'title': 'Dwarven Realms (Steam) Giveaway',  # 키 배포가 아닌 것처럼 위장한 항목
                'type': 'Game',
                'status': 'Active',
                'platforms': 'PC, Steam',
                'open_giveaway_url': 'https://www.gamerpower.com/open/dwarven-realms-steam-key-giveaway',
            }
        ]
        install(giveaway_service, FakeHttp({GAMERPOWER_ENDPOINT: payload, STEAM_APPDETAILS_ENDPOINT: steam_appdetails}, REDIRECTS), monkeypatch)
        giveaway_service.stores = frozenset({Store.STEAM})

        assert await giveaway_service.find_new() == []

    async def test_key_drop_survives_paid_store_price(self, giveaway_service: GiveawayService, http: FakeHttp, monkeypatch, frozen_now):
        """키 배포는 스토어 가격과 무관하게 이뤄지므로 가격 검증을 적용하면 안 된다."""
        install(giveaway_service, http, monkeypatch)
        giveaway_service.stores = frozenset({Store.STEAM})

        dwarven = next(item for item in await giveaway_service.find_new() if 'Dwarven' in item.title)

        assert dwarven.claim_kind is ClaimKind.KEY_DROP
        # 무료가 아니어도 메타데이터는 보강한다. (이 게임은 Steam이 장르를 주지 않는다.)
        assert dwarven.description
        assert dwarven.thumbnail_url.startswith('https://')
        assert dwarven.original_price == '₩ 11,000'

    async def test_enrichment_failure_does_not_block_announcement(
        self, giveaway_service: GiveawayService, monkeypatch, frozen_now, gamerpower_payload
    ):
        """Steam 조회가 실패했다고 발행을 막으면, 스토어 장애 때 알림이 통째로 멈춘다."""
        install(giveaway_service, FakeHttp({GAMERPOWER_ENDPOINT: gamerpower_payload}, REDIRECTS), monkeypatch)
        giveaway_service.stores = frozenset({Store.STEAM})

        titles = {item.title for item in await giveaway_service.find_new()}

        assert titles == {'Deponia', 'Dwarven Realms'}

    async def test_unknown_appid_is_left_alone(self, giveaway_service: GiveawayService, monkeypatch, frozen_now, gamerpower_payload):
        install(giveaway_service, FakeHttp({GAMERPOWER_ENDPOINT: gamerpower_payload, STEAM_APPDETAILS_ENDPOINT: {}}, REDIRECTS), monkeypatch)
        giveaway_service.stores = frozenset({Store.STEAM})

        assert len(await giveaway_service.find_new()) == 2

    async def test_non_steam_stores_skip_enrichment(self, giveaway_service: GiveawayService, http: FakeHttp, monkeypatch, frozen_now):
        install(giveaway_service, http, monkeypatch)
        giveaway_service.stores = frozenset({Store.EPIC})

        await giveaway_service.find_new()

        assert all(endpoint != STEAM_APPDETAILS_ENDPOINT for endpoint, _ in http.requests)


class TestFindNew:
    async def test_announced_items_are_not_returned_again(self, giveaway_service: GiveawayService, http: FakeHttp, monkeypatch, frozen_now):
        install(giveaway_service, http, monkeypatch)
        giveaway_service.stores = frozenset({Store.STEAM, Store.EPIC})

        first = await giveaway_service.find_new()
        await giveaway_service.repository.mark_all_announced(first)
        second = await giveaway_service.find_new()

        assert first
        assert second == []

    async def test_enrichment_runs_only_for_new_items(self, giveaway_service: GiveawayService, http: FakeHttp, monkeypatch, frozen_now):
        install(giveaway_service, http, monkeypatch)
        giveaway_service.stores = frozenset({Store.STEAM})

        await giveaway_service.repository.mark_all_announced(await giveaway_service.find_new())
        calls_before = sum(1 for endpoint, _ in http.requests if endpoint == STEAM_APPDETAILS_ENDPOINT)
        await giveaway_service.find_new()

        assert calls_before > 0
        assert sum(1 for endpoint, _ in http.requests if endpoint == STEAM_APPDETAILS_ENDPOINT) == calls_before
