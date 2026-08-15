"""공통 픽스처.

기본적으로 모든 테스트는 외부 네트워크 없이 동작한다.
실제 PUBG API를 호출하는 테스트는 `network` 마커를 달고, 토큰이 없으면 자동으로 건너뛴다.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from ks_bot.bot import KSBot
from ks_bot.common.timeutil import Timezone
from ks_bot.config import Settings, load_dotenv
from ks_bot.core.giveaway import GiveawayService
from ks_bot.core.giveaway_repository import GiveawayRepository
from ks_bot.core.pubg import PubgBalancer
from ks_bot.core.repository import PlayerRepository

# 로컬 `.env`에 PUBG_TOKEN이 있으면 network 마커 테스트를 그대로 실행할 수 있게 한다.
load_dotenv()

FIXTURES_DIR = Path(__file__).parent / 'fixtures'

# 무료 배포 픽스처를 수집한 시각. 픽스처 안의 배포 기간이 이 시점을 기준으로 하므로,
# 실제 현재 시각을 쓰면 시간이 지날수록 테스트 결과가 바뀐다.
FIXTURE_NOW = datetime(2026, 8, 16, 12, 0, tzinfo=Timezone.KST.zone)


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES_DIR / name).read_text(encoding='utf-8'))


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
async def bot(settings: Settings) -> AsyncIterator[KSBot]:
    """디스코드 게이트웨이에 접속하지 않는 봇 인스턴스."""
    instance = KSBot(settings)
    try:
        yield instance
    finally:
        await instance.close()


@pytest.fixture
def epic_payload() -> dict:
    return load_fixture('epic_free_games.json')


@pytest.fixture
def gamerpower_payload() -> list[dict]:
    return load_fixture('gamerpower_giveaways.json')


@pytest.fixture
def steam_appdetails() -> dict:
    return load_fixture('steam_appdetails.json')


@pytest.fixture
def frozen_now(monkeypatch: pytest.MonkeyPatch) -> datetime:
    """현재 시각을 픽스처 수집 시점으로 고정한다.

    배포의 진행/예정/마감 판정이 전부 현재 시각에 의존하므로, 고정하지 않으면
    똑같은 픽스처로도 시간이 지나면 다른 결과가 나온다.
    """
    for module in ('ks_bot.common.giveaway', 'ks_bot.core.giveaway', 'ks_bot.core.giveaway_repository'):
        monkeypatch.setattr(f'{module}.datetime_now', lambda *args, **kwargs: FIXTURE_NOW)
    return FIXTURE_NOW


@pytest.fixture
async def giveaway_repository(db_path: Path) -> AsyncIterator[GiveawayRepository]:
    repo = GiveawayRepository(db_path)
    await repo.connect(reset=True)
    try:
        yield repo
    finally:
        await repo.close()


@pytest.fixture
async def giveaway_service(db_path: Path) -> AsyncIterator[GiveawayService]:
    """네트워크를 타지 않는 배포 서비스. API 호출은 테스트에서 monkeypatch한다."""
    service = GiveawayService(db_path)
    await service.connect()
    try:
        yield service
    finally:
        await service.aclose()


@pytest.fixture
async def balancer(db_path: Path) -> AsyncIterator[PubgBalancer]:
    """네트워크를 타지 않는 밸런서. API 호출은 테스트에서 monkeypatch한다."""
    service = PubgBalancer(api_key='test-token', platform='steam', db_path=db_path, db_reset=True, max_match_num=4)
    await service.connect()
    try:
        yield service
    finally:
        await service.aclose()
