"""무료 배포 발행 이력 저장소.

폴링 봇의 대표적인 실패 모드는 같은 배포를 반복해서 올리는 것이다.
발행한 항목을 (상품 키, 단계)로 기록해 두고, 새 항목만 골라낸다.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

import aiosqlite

from ks_bot.common.giveaway import ClaimKind, Giveaway, Store
from ks_bot.common.timeutil import datetime_now, parse_utc_to_datetime, to_iso
from ks_bot.core.sqlite import SqliteRepository
from ks_bot.logging_config import get_logger

__all__ = ['GiveawayRepository']

logger = get_logger(__name__)

_GIVEAWAYS_TABLE = 'giveaways'

# 종료 시각이 이만큼 뒤로 밀려야 "다시 배포됐다"고 본다.
# 수집처가 마감을 몇 시간 단위로 정정하는 일이 흔해서, 그 정도로는 재발행하지 않는다.
_REDISTRIBUTION_THRESHOLD = timedelta(days=1)

# 중계 링크 해석에 실패한 기록을 이 기간 동안 유지한다(일시적 장애면 이후 재시도된다).
_NEGATIVE_CACHE_TTL = timedelta(hours=12)

_CREATE_GIVEAWAYS_TABLE = f"""
CREATE TABLE IF NOT EXISTS {_GIVEAWAYS_TABLE} (
    key          TEXT NOT NULL,
    phase        TEXT NOT NULL,
    title        TEXT,
    store        TEXT,
    url          TEXT,
    starts_at    DATETIME,
    ends_at      DATETIME,
    payload      TEXT,
    announced_at DATETIME,
    message_id   INTEGER,
    PRIMARY KEY (key, phase)
);
"""

_URL_CACHE_TABLE = 'giveaway_url_cache'

# 중계 링크 → 실제 스토어 URL 변환은 네트워크 요청이 필요하므로 결과를 캐시한다.
# 이 값이 상품 식별자를 결정하기 때문에, 폴링마다 다시 조회하면 비용이 그대로 늘어난다.
_CREATE_URL_CACHE_TABLE = f"""
CREATE TABLE IF NOT EXISTS {_URL_CACHE_TABLE} (
    source_url TEXT PRIMARY KEY,
    final_url  TEXT,
    cached_at  DATETIME
);
"""

_CREATE_INDEXES = (f'CREATE INDEX IF NOT EXISTS idx_giveaways_ends_at ON {_GIVEAWAYS_TABLE}(ends_at);',)


def _phase_of(giveaway: Giveaway) -> str:
    """예정 배포와 진행 중 배포를 각각 한 번씩 알리기 위한 단계 구분."""
    return 'upcoming' if giveaway.is_upcoming else 'active'


def _serialize(giveaway: Giveaway) -> str:
    return json.dumps(
        {
            'store': giveaway.store.value,
            'product_id': giveaway.product_id,
            'title': giveaway.title,
            'url': giveaway.url,
            'claim_kind': giveaway.claim_kind.value,
            'description': giveaway.description,
            'genres': list(giveaway.genres),
            'original_price': giveaway.original_price,
            'thumbnail_url': giveaway.thumbnail_url,
            'starts_at': to_iso(giveaway.starts_at) if giveaway.starts_at else None,
            'ends_at': to_iso(giveaway.ends_at) if giveaway.ends_at else None,
            'is_dlc': giveaway.is_dlc,
            'metacritic': giveaway.metacritic,
            'source': giveaway.source,
            'extra_urls': list(giveaway.extra_urls),
        },
        ensure_ascii=False,
    )


def _deserialize(raw: str) -> Giveaway:
    data: dict[str, Any] = json.loads(raw)
    return Giveaway(
        store=Store(data.get('store', Store.OTHER.value)),
        product_id=data.get('product_id', ''),
        title=data.get('title', ''),
        url=data.get('url', ''),
        claim_kind=ClaimKind(data.get('claim_kind', ClaimKind.STORE_FREE.value)),
        description=data.get('description', ''),
        genres=tuple(data.get('genres') or ()),
        original_price=data.get('original_price', ''),
        thumbnail_url=data.get('thumbnail_url', ''),
        starts_at=parse_utc_to_datetime(data['starts_at']) if data.get('starts_at') else None,
        ends_at=parse_utc_to_datetime(data['ends_at']) if data.get('ends_at') else None,
        is_dlc=bool(data.get('is_dlc', False)),
        metacritic=int(data.get('metacritic') or 0),
        source=data.get('source', ''),
        extra_urls=tuple(data.get('extra_urls') or ()),
    )


class GiveawayRepository(SqliteRepository):
    """무료 배포 발행 이력 저장소."""

    TABLES = (
        (_GIVEAWAYS_TABLE, _CREATE_GIVEAWAYS_TABLE),
        (_URL_CACHE_TABLE, _CREATE_URL_CACHE_TABLE),
    )
    INDEXES = _CREATE_INDEXES

    # ---------- 중계 링크 캐시 ----------

    async def get_cached_url(self, source_url: str, *, negative_ttl: timedelta = _NEGATIVE_CACHE_TTL) -> str | None:
        """캐시된 최종 URL.

        Returns:
            해석된 URL, 해석에 실패했다고 확정된 경우 빈 문자열, 다시 시도해야 하면 None.

        해석 실패도 기록해 둔다. 그러지 않으면 끝내 해석되지 않는 링크(itch.io 소규모 배포 등)를
        폴링마다 다시 두드리게 된다. 다만 일시적 장애일 수도 있어 일정 시간이 지나면 재시도한다.
        """
        row = await self._fetch_one(f'SELECT final_url, cached_at FROM {_URL_CACHE_TABLE} WHERE source_url = ?', (source_url,))
        if row is None:
            return None
        if row['final_url']:
            return row['final_url']

        if not row['cached_at']:
            return None
        return '' if datetime_now() - parse_utc_to_datetime(row['cached_at']) < negative_ttl else None

    async def cache_url(self, source_url: str, final_url: str) -> None:
        await self._execute(
            f"""
            INSERT INTO {_URL_CACHE_TABLE} (source_url, final_url, cached_at) VALUES (?, ?, ?)
            ON CONFLICT(source_url) DO UPDATE SET final_url = excluded.final_url, cached_at = excluded.cached_at
            """,
            (source_url, final_url, to_iso(datetime_now())),
        )

    # ---------- 발행 이력 ----------

    async def count(self) -> int:
        row = await self._fetch_one(f'SELECT COUNT(*) AS n FROM {_GIVEAWAYS_TABLE}')
        return int(row['n']) if row else 0

    async def is_empty(self) -> bool:
        """한 번도 발행한 적이 없는 상태인지.

        최초 실행 시 진행 중인 배포를 전부 쏟아내지 않도록, 호출자가 이 값으로 판단한다.
        """
        return await self.count() == 0

    async def _announced_ends_at(self, keys: Iterable[str]) -> dict[tuple[str, str], datetime | None]:
        key_list = list(dict.fromkeys(keys))
        if not key_list:
            return {}

        placeholders = ', '.join('?' for _ in key_list)
        rows = await self._fetch_all(
            f'SELECT key, phase, ends_at FROM {_GIVEAWAYS_TABLE} WHERE key IN ({placeholders})',
            key_list,
        )
        return {(row['key'], row['phase']): (parse_utc_to_datetime(row['ends_at']) if row['ends_at'] else None) for row in rows}

    async def filter_unannounced(self, giveaways: Iterable[Giveaway]) -> list[Giveaway]:
        """아직 알리지 않은 배포만 골라낸다.

        같은 상품이라도 예정 → 진행 단계로 넘어가면 한 번 더 알린다.
        예전에 끝난 배포가 다시 풀린 경우(종료 시각이 하루 이상 미래로 이동)도 새 배포로 본다.
        """
        candidates = list(giveaways)
        known = await self._announced_ends_at(g.key for g in candidates)

        fresh: list[Giveaway] = []
        for giveaway in candidates:
            identity = (giveaway.key, _phase_of(giveaway))
            if identity not in known:
                fresh.append(giveaway)
                continue

            previous_end = known[identity]
            if giveaway.ends_at and previous_end and giveaway.ends_at > previous_end + _REDISTRIBUTION_THRESHOLD:
                logger.info('재배포로 판단합니다: %s (이전 종료 %s → %s)', giveaway.key, previous_end, giveaway.ends_at)
                fresh.append(giveaway)
        return fresh

    async def mark_announced(self, giveaway: Giveaway, message_id: int | None = None) -> None:
        await self._execute(
            f"""
            INSERT INTO {_GIVEAWAYS_TABLE}
                (key, phase, title, store, url, starts_at, ends_at, payload, announced_at, message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(key, phase) DO UPDATE SET
                title        = excluded.title,
                url          = excluded.url,
                starts_at    = excluded.starts_at,
                ends_at      = excluded.ends_at,
                payload      = excluded.payload,
                announced_at = excluded.announced_at,
                message_id   = excluded.message_id
            """,
            (
                giveaway.key,
                _phase_of(giveaway),
                giveaway.title,
                giveaway.store.value,
                giveaway.url,
                to_iso(giveaway.starts_at) if giveaway.starts_at else None,
                to_iso(giveaway.ends_at) if giveaway.ends_at else None,
                _serialize(giveaway),
                to_iso(datetime_now()),
                int(message_id) if message_id is not None else None,
            ),
        )

    async def mark_all_announced(self, giveaways: Iterable[Giveaway], message_id: int | None = None) -> None:
        for giveaway in giveaways:
            await self.mark_announced(giveaway, message_id)

    async def list_active(self) -> list[Giveaway]:
        """아직 마감되지 않은, 진행 중인 배포 목록(마감 임박 순)."""
        rows = await self._fetch_all(
            f"SELECT payload FROM {_GIVEAWAYS_TABLE} WHERE phase = 'active' AND payload IS NOT NULL",
        )
        active = [item for item in (_safe_deserialize(row) for row in rows) if item and not item.is_expired]
        # 마감 시각이 없는 항목(상시 배포)은 뒤로 보낸다.
        return sorted(active, key=lambda g: (g.ends_at is None, g.ends_at or datetime_now()))

    async def purge_expired(self, grace_period: timedelta = timedelta(days=30)) -> int:
        """오래전에 끝난 기록을 지운다. 재배포 판정을 위해 얼마간은 남겨둔다."""
        cutoff = to_iso(datetime_now() - grace_period)
        async with self.conn.execute(
            f'DELETE FROM {_GIVEAWAYS_TABLE} WHERE ends_at IS NOT NULL AND ends_at < ?',
            (cutoff,),
        ) as cursor:
            deleted = cursor.rowcount
        await self.conn.commit()
        return max(0, deleted)


def _safe_deserialize(row: aiosqlite.Row) -> Giveaway | None:
    try:
        return _deserialize(row['payload'])
    except (TypeError, ValueError, KeyError):
        logger.warning('저장된 배포 정보를 복원하지 못했습니다. 건너뜁니다.')
        return None
