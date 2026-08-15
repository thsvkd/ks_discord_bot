"""실제 PUBG API를 호출하는 통합 테스트.

`PUBG_TOKEN`이 설정된 경우에만 실행된다. (`pytest -m network`)
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest

from ks_bot.common.errors import PlayerNotFoundError
from ks_bot.core.pubg import DEFAULT_CLAN_ID, PubgBalancer

pytestmark = pytest.mark.network

REAL_PLAYER_NAME = 'SonPANG'


@pytest.fixture
async def live_balancer(tmp_path) -> AsyncIterator[PubgBalancer]:
    service = PubgBalancer(
        api_key=os.environ.get('PUBG_TOKEN', ''),
        platform='steam',
        db_path=tmp_path / 'live.db',
        db_reset=True,
    )
    async with service:
        yield service


async def test_fetch_player_by_name(live_balancer: PubgBalancer):
    player = await live_balancer.fetch_player_by_name(REAL_PLAYER_NAME)

    assert player.name == REAL_PLAYER_NAME
    assert player.platform == 'steam'
    assert player.id.startswith('account.')
    assert player.normalized_id and '-' not in player.normalized_id
    # PUBG API는 최근 14일 이내 매치만 돌려주므로, 목록이 비어 있을 수 있다.
    assert isinstance(player.match_list, list)


async def test_player_is_cached_after_fetch(live_balancer: PubgBalancer):
    fetched = await live_balancer.get_player(REAL_PLAYER_NAME)
    cached = await live_balancer.repository.get_player(player_name=REAL_PLAYER_NAME)

    assert cached == fetched


async def test_unknown_player_raises(live_balancer: PubgBalancer):
    with pytest.raises(PlayerNotFoundError):
        await live_balancer.fetch_player_by_name('절대_존재하지_않는_플레이어_이름_12345')


async def test_current_season(live_balancer: PubgBalancer):
    season = await live_balancer.fetch_current_season()
    assert season['attributes']['isCurrentSeason'] is True


async def test_clan_data(live_balancer: PubgBalancer):
    clan = await live_balancer.fetch_clan(DEFAULT_CLAN_ID)
    assert clan['data']['attributes']['clanName']
