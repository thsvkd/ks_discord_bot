"""공통 픽스처.

기본적으로 모든 테스트는 외부 네트워크 없이 동작한다.
실제 PUBG API를 호출하는 테스트는 `network` 마커를 달고, 토큰이 없으면 자동으로 건너뛴다.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from ks_bot.config import Settings
from ks_bot.core.pubg import PubgBalancer
from ks_bot.core.repository import PlayerRepository


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """PUBG 토큰이 없으면 네트워크 테스트를 건너뛴다."""
    if os.environ.get('PUBG_TOKEN'):
        return

    skip_network = pytest.mark.skip(reason='PUBG_TOKEN 환경 변수가 없어 네트워크 테스트를 건너뜁니다.')
    for item in items:
        if 'network' in item.keywords:
            item.add_marker(skip_network)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / 'test_history.db'


@pytest.fixture
async def repository(db_path: Path) -> AsyncIterator[PlayerRepository]:
    repo = PlayerRepository(db_path)
    await repo.connect(reset=True)
    try:
        yield repo
    finally:
        await repo.close()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        discord_token='test-discord-token',
        pubg_token='test-pubg-token',
        db_path=tmp_path / 'history.db',
        game_result_dir=tmp_path / 'game_result',
    )


@pytest.fixture
async def balancer(db_path: Path) -> AsyncIterator[PubgBalancer]:
    """네트워크를 타지 않는 밸런서. API 호출은 테스트에서 monkeypatch한다."""
    service = PubgBalancer(api_key='test-token', platform='steam', db_path=db_path, db_reset=True, max_match_num=4)
    await service.connect()
    try:
        yield service
    finally:
        await service.aclose()
