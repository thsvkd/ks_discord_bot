"""무료 배포 수집 서비스.

수집처는 두 곳이다.

- **Epic 공식 API**: Epic 배포에 대해 가장 정확하다. 가격/기간/한국어 설명이 모두 들어 있다.
- **GamerPower**: Steam·GOG·itch 등 나머지 스토어를 폭넓게 커버한다.

두 응답 모두 구조화되어 있어 별도의 자연어 처리 없이 파싱만으로 필요한 정보가 나온다.
부족한 한국어 설명·장르·이미지는 Steam `appdetails`로 보강한다.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Collection, Iterable
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any
from urllib.parse import urlparse

from ks_bot.common.errors import KSBotError
from ks_bot.common.giveaway import ClaimKind, Giveaway, Store, clean_title, has_desktop_platform, strip_promo_sentences
from ks_bot.common.timeutil import datetime_now, parse_utc_to_datetime
from ks_bot.core.giveaway_repository import GiveawayRepository
from ks_bot.core.http_client import ApiClient
from ks_bot.logging_config import get_logger

__all__ = [
    'EPIC_ENDPOINT',
    'GAMERPOWER_ENDPOINT',
    'STEAM_APPDETAILS_ENDPOINT',
    'GiveawayService',
    'identify_product',
    'merge_giveaways',
    'parse_epic_payload',
    'parse_gamerpower_payload',
]

logger = get_logger(__name__)

EPIC_ENDPOINT = 'https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions'
EPIC_PRODUCT_URL = 'https://store.epicgames.com/p/{slug}'
GAMERPOWER_ENDPOINT = 'https://www.gamerpower.com/api/giveaways'
STEAM_APPDETAILS_ENDPOINT = 'https://store.steampowered.com/api/appdetails'

# GamerPower의 중계 링크(`/open/...`)는 봇처럼 보이는 요청에 403을 준다.
# 일반 브라우저 헤더를 붙여야 실제 스토어 주소로 리다이렉트된다.
BROWSER_HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'),
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
}

SOURCE_EPIC = 'epic'
SOURCE_GAMERPOWER = 'gamerpower'

# 같은 상품을 여러 수집처가 들고 있을 때, 어느 쪽 정보를 우선할지.
_SOURCE_PRIORITY = {SOURCE_EPIC: 2, SOURCE_GAMERPOWER: 1}

# Epic 이미지 중 임베드에 쓰기 좋은 순서.
_EPIC_IMAGE_PREFERENCE = ('OfferImageWide', 'DieselStoreFrontWide', 'featuredMedia', 'Thumbnail', 'OfferImageTall')

_STEAM_APP_PATTERN = re.compile(r'/app/(\d+)')
_EPIC_PRODUCT_PATTERN = re.compile(r'/p/([^/?#]+)')
_GOG_PATTERN = re.compile(r'/game/([^/?#]+)')
# `Dwarven Realms (Steam) Key Giveaway`처럼 수량이 정해진 키 배포를 구분한다.
_KEY_DROP_PATTERN = re.compile(r'\bkeys?\b', re.IGNORECASE)


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _steam_original_price(price_overview: dict) -> str:
    """할인 전 정가 문자열.

    Steam은 할인 중일 때만 `initial_formatted`를 채우고, 할인이 없으면 빈 문자열을 준다.
    (그때는 `final_formatted`가 정가다.) 한쪽만 보면 가격이 통째로 비어 버린다.
    """
    initial = (price_overview.get('initial_formatted') or '').strip()
    return initial or (price_overview.get('final_formatted') or '').strip()


# ---------- URL 해석 ----------


def identify_product(url: str) -> tuple[Store, str]:
    """스토어 URL에서 (스토어, 상품 식별자)를 뽑는다.

    상품 식별자는 중복 판정 키의 재료이므로, 추적 파라미터나 로케일이 붙어도
    변하지 않는 값이어야 한다. Steam은 앱 ID, Epic/GOG는 슬러그를 쓴다.
    """
    store = Store.from_url(url)
    patterns = {Store.STEAM: _STEAM_APP_PATTERN, Store.EPIC: _EPIC_PRODUCT_PATTERN, Store.GOG: _GOG_PATTERN}

    pattern = patterns.get(store)
    if pattern is not None:
        match = pattern.search(url)
        if match:
            return store, match.group(1)

    parsed = urlparse(url)
    fallback = f'{parsed.netloc}{parsed.path}'.rstrip('/').lower()
    return store, fallback or url


# ---------- Epic ----------


def _epic_offers(promotions: dict, field_name: str) -> Iterable[dict]:
    for group in (promotions or {}).get(field_name) or []:
        yield from group.get('promotionalOffers') or []


def _offer_window(offer: dict) -> tuple[datetime | None, datetime | None]:
    def parse(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return parse_utc_to_datetime(value)
        except ValueError:
            logger.warning('배포 기간을 파싱하지 못했습니다: %r', value)
            return None

    return parse(offer.get('startDate')), parse(offer.get('endDate'))


def _epic_free_window(element: dict, now: datetime) -> tuple[datetime, datetime] | None:
    """무료 배포 구간을 찾는다. 무료가 아니면 None.

    진행 중인 건은 실제 판매가가 0인지로 판정한다(가장 확실한 신호다).
    아직 시작하지 않은 건은 판매가가 아직 정가이므로 할인율 0%로 판정하는데,
    이 API는 단순 할인 예정(20%, 25% 등)도 같이 돌려주기 때문에 이 검사가 반드시 필요하다.
    """
    total = ((element.get('price') or {}).get('totalPrice')) or {}
    original_price = _to_int(total.get('originalPrice'))
    discount_price = _to_int(total.get('discountPrice'))
    promotions = element.get('promotions') or {}

    if discount_price == 0:
        for offer in _epic_offers(promotions, 'promotionalOffers'):
            start, end = _offer_window(offer)
            if start and end and start <= now < end:
                return start, end

    for offer in _epic_offers(promotions, 'upcomingPromotionalOffers'):
        if _to_int((offer.get('discountSetting') or {}).get('discountPercentage')) != 0:
            continue
        # 원래 값이 0원인 항목(상시 무료 아이템)은 알릴 가치가 없다.
        if original_price <= 0:
            continue
        start, end = _offer_window(offer)
        if start and end and start > now:
            return start, end

    return None


def _epic_slug(element: dict) -> str:
    """상품 페이지 슬러그를 찾는다.

    `productSlug`는 비어 있거나 `cardpocalypse/home`처럼 접미사가 붙는 경우가 많아
    믿을 수 없다. 매핑 정보를 먼저 본다.
    """
    for mapping in element.get('offerMappings') or []:
        if mapping.get('pageSlug'):
            return str(mapping['pageSlug'])
    for mapping in (element.get('catalogNs') or {}).get('mappings') or []:
        if mapping.get('pageSlug'):
            return str(mapping['pageSlug'])

    slug = element.get('productSlug') or element.get('urlSlug') or ''
    return str(slug).split('/')[0]


def _epic_image(element: dict) -> str:
    images = {image.get('type'): image.get('url') for image in element.get('keyImages') or [] if image.get('url')}
    for image_type in _EPIC_IMAGE_PREFERENCE:
        if images.get(image_type):
            return str(images[image_type])
    return next(iter(images.values()), '') if images else ''


def parse_epic_payload(payload: dict, *, now: datetime | None = None) -> list[Giveaway]:
    """Epic `freeGamesPromotions` 응답을 정규화한다."""
    now = now or datetime_now()
    elements = ((payload.get('data') or {}).get('Catalog') or {}).get('searchStore', {}).get('elements') or []

    giveaways: list[Giveaway] = []
    for element in elements:
        slug = _epic_slug(element)
        if not slug:
            continue

        window = _epic_free_window(element, now)
        if window is None:
            continue

        starts_at, ends_at = window
        total = ((element.get('price') or {}).get('totalPrice')) or {}
        giveaways.append(
            Giveaway(
                store=Store.EPIC,
                product_id=slug,
                title=(element.get('title') or '').strip(),
                url=EPIC_PRODUCT_URL.format(slug=slug),
                claim_kind=ClaimKind.STORE_FREE,
                description=(element.get('description') or '').strip(),
                original_price=((total.get('fmtPrice') or {}).get('originalPrice') or '').strip(),
                thumbnail_url=_epic_image(element),
                starts_at=starts_at,
                ends_at=ends_at,
                is_dlc=(element.get('offerType') or 'BASE_GAME') != 'BASE_GAME',
                source=SOURCE_EPIC,
            )
        )
    return giveaways


# ---------- GamerPower ----------


def _parse_gamerpower_date(value: str | None) -> datetime | None:
    """`2026-08-17 23:59:00` 형식(UTC)을 파싱한다. `N/A`는 마감 없음으로 본다."""
    text = (value or '').strip()
    if not text or text.upper() == 'N/A':
        return None
    try:
        return parse_utc_to_datetime(text.replace(' ', 'T'))
    except ValueError:
        logger.warning('마감 시각을 파싱하지 못했습니다: %r', value)
        return None


def _gamerpower_worth(value: str | None) -> str:
    text = (value or '').strip()
    return '' if text.upper() in ('', 'N/A', 'FREE') else text


def parse_gamerpower_payload(payload: list[dict]) -> list[Giveaway]:
    """GamerPower `giveaways` 응답을 정규화한다.

    이 시점의 `product_id`는 임시값이다. 실제 스토어 주소는 중계 링크를 따라가야
    알 수 있으므로, `GiveawayService`가 URL을 해석한 뒤 최종 식별자로 교체한다.
    """
    giveaways: list[Giveaway] = []
    for item in payload or []:
        if (item.get('status') or '').strip().lower() != 'active':
            continue
        if (item.get('type') or '').strip().lower() != 'game':
            continue

        platforms = item.get('platforms') or ''
        if not has_desktop_platform(platforms):
            continue

        url = item.get('open_giveaway_url') or item.get('open_giveaway') or item.get('gamerpower_url') or ''
        if not url:
            continue

        raw_title = item.get('title') or ''
        giveaways.append(
            Giveaway(
                store=Store.from_platforms(platforms),
                product_id=f'gp{item.get("id", "")}',
                title=clean_title(raw_title) or raw_title.strip(),
                url=url,
                claim_kind=ClaimKind.KEY_DROP if _KEY_DROP_PATTERN.search(raw_title) else ClaimKind.STORE_FREE,
                description=strip_promo_sentences(item.get('description') or ''),
                original_price=_gamerpower_worth(item.get('worth')),
                thumbnail_url=item.get('image') or item.get('thumbnail') or '',
                ends_at=_parse_gamerpower_date(item.get('end_date')),
                source=SOURCE_GAMERPOWER,
            )
        )
    return giveaways


# ---------- 병합 ----------


def merge_giveaways(items: Iterable[Giveaway]) -> list[Giveaway]:
    """같은 상품을 가리키는 항목을 하나로 합친다.

    Epic 공식 정보가 GamerPower보다 정확하므로 우선하고, 비어 있는 항목만 보완한다.
    """
    merged: dict[str, Giveaway] = {}
    for item in items:
        existing = merged.get(item.key)
        if existing is None:
            merged[item.key] = item
            continue

        item_priority = _SOURCE_PRIORITY.get(item.source, 0)
        existing_priority = _SOURCE_PRIORITY.get(existing.source, 0)
        primary, secondary = (item, existing) if item_priority > existing_priority else (existing, item)
        merged[item.key] = primary.merged_with(secondary)
    return list(merged.values())


def sort_for_display(giveaways: Iterable[Giveaway]) -> list[Giveaway]:
    """진행 중 → 예정 순, 각 그룹 안에서는 마감이 빠른 순."""
    far_future = datetime.max.replace(tzinfo=datetime_now().tzinfo)
    return sorted(giveaways, key=lambda g: (g.is_upcoming, g.ends_at or far_future, g.title))


# ---------- 서비스 ----------


class GiveawayService:
    """무료 배포를 수집·정규화하고, 아직 알리지 않은 항목을 골라낸다."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        stores: Collection[Store] | None = None,
        include_upcoming: bool = True,
        include_dlc: bool = False,
        timeout: float = 15.0,
        repository: GiveawayRepository | None = None,
    ):
        self.repository = repository or GiveawayRepository(db_path)
        self.stores = frozenset(stores) if stores else None
        self.include_upcoming = include_upcoming
        self.include_dlc = include_dlc
        self._client = ApiClient(api_key='', base_url='', timeout=timeout, default_headers=BROWSER_HEADERS)

    async def __aenter__(self) -> GiveawayService:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def connect(self) -> GiveawayService:
        await self.repository.connect()
        return self

    async def aclose(self) -> None:
        await self._client.aclose()
        await self.repository.close()

    # ---------- 수집 ----------

    async def _request(self, endpoint: str, params: dict | None = None) -> Any:
        return await self._client.request(endpoint, params=params, header=BROWSER_HEADERS)

    async def fetch_epic(self) -> list[Giveaway]:
        payload = await self._request(EPIC_ENDPOINT, params={'locale': 'ko', 'country': 'KR', 'allowCountries': 'KR'})
        return parse_epic_payload(payload)

    async def fetch_gamerpower(self) -> list[Giveaway]:
        payload = await self._request(GAMERPOWER_ENDPOINT, params={'type': 'game'})
        return parse_gamerpower_payload(payload)

    async def collect(self) -> list[Giveaway]:
        """모든 수집처에서 배포 목록을 모아 정규화한다.

        수집처 하나가 죽어도 나머지는 그대로 동작한다.
        """
        results = await asyncio.gather(self.fetch_epic(), self.fetch_gamerpower(), return_exceptions=True)

        collected: list[Giveaway] = []
        for source_name, result in zip(('Epic', 'GamerPower'), results, strict=False):
            if isinstance(result, BaseException):
                logger.warning('%s 수집에 실패했습니다: %s', source_name, result)
                continue
            collected.extend(result)

        resolved = await self._resolve_urls(collected)
        return sort_for_display(item for item in merge_giveaways(resolved) if self._is_wanted(item))

    async def find_new(self) -> list[Giveaway]:
        """아직 알리지 않은 배포만 골라 상세 정보를 채운다."""
        fresh = await self.repository.filter_unannounced(await self.collect())
        enriched = await self._enrich(fresh)
        return sort_for_display(item for item in enriched if self._is_wanted(item))

    def _is_wanted(self, giveaway: Giveaway) -> bool:
        if self.stores is not None and giveaway.store not in self.stores:
            return False
        if giveaway.is_dlc and not self.include_dlc:
            return False
        if giveaway.is_upcoming and not self.include_upcoming:
            return False
        return not giveaway.is_expired

    # ---------- 중계 링크 해석 ----------

    def _store_may_be_wanted(self, store: Store) -> bool:
        """중계 링크를 해석할 가치가 있는 스토어인지.

        수집처가 알려준 스토어가 이미 대상 밖이면 해석할 이유가 없다.
        다만 판별에 실패한(OTHER) 항목은 실제 주소를 봐야 알 수 있으므로 해석한다.
        """
        return self.stores is None or store in self.stores or store is Store.OTHER

    async def _resolve_urls(self, giveaways: Iterable[Giveaway]) -> list[Giveaway]:
        resolved: list[Giveaway] = []
        for giveaway in giveaways:
            if giveaway.source != SOURCE_GAMERPOWER or not self._store_may_be_wanted(giveaway.store):
                resolved.append(giveaway)
                continue

            final_url = await self._final_url(giveaway.url)
            if not final_url or final_url == giveaway.url:
                resolved.append(giveaway)
                continue

            store, product_id = identify_product(final_url)
            resolved.append(
                replace(
                    giveaway,
                    url=final_url,
                    store=store if store is not Store.OTHER else giveaway.store,
                    product_id=product_id,
                    extra_urls=(giveaway.url,),
                )
            )
        return resolved

    async def _final_url(self, url: str) -> str:
        # 빈 문자열은 "해석 불가로 확정"이라는 뜻이므로 None과 구분해야 한다.
        cached = await self.repository.get_cached_url(url)
        if cached is not None:
            return cached

        try:
            final_url = await self._client.resolve_final_url(url, header=BROWSER_HEADERS)
        except KSBotError as e:
            logger.warning('중계 링크를 해석하지 못했습니다: %s (%s)', url, e)
            await self.repository.cache_url(url, '')
            return ''

        if not final_url or final_url == url:
            await self.repository.cache_url(url, '')
            return ''

        await self.repository.cache_url(url, final_url)
        return final_url

    # ---------- 상세 정보 보강 ----------

    async def _enrich(self, giveaways: Iterable[Giveaway]) -> list[Giveaway]:
        enriched: list[Giveaway] = []
        for giveaway in giveaways:
            if giveaway.store is not Store.STEAM or not giveaway.product_id.isdigit():
                enriched.append(giveaway)
                continue

            detailed = await self._enrich_with_steam(giveaway)
            if detailed is not None:
                enriched.append(detailed)
        return enriched

    async def _enrich_with_steam(self, giveaway: Giveaway) -> Giveaway | None:
        """Steam 상세 정보로 보강한다. 실제로 무료가 아니면 None을 돌려준다.

        조회 자체가 실패한 경우에는 원본을 그대로 돌려준다.
        보강은 부가 기능이므로, 실패했다고 발행을 막으면 안 된다.
        """
        try:
            payload = await self._request(STEAM_APPDETAILS_ENDPOINT, params={'appids': giveaway.product_id, 'cc': 'kr', 'l': 'korean'})
        except KSBotError as e:
            logger.warning('Steam 상세 정보를 가져오지 못했습니다: %s (%s)', giveaway.title, e)
            return giveaway

        entry = (payload or {}).get(giveaway.product_id) or {}
        if not entry.get('success'):
            return giveaway

        data = entry.get('data') or {}
        price = data.get('price_overview') or {}
        is_actually_free = bool(data.get('is_free')) or price.get('discount_percent') == 100 or price.get('final') == 0

        # 키 배포는 스토어 가격과 무관하게 이뤄지므로 이 검사를 적용하지 않는다.
        if giveaway.claim_kind is ClaimKind.STORE_FREE and not is_actually_free:
            logger.info('스토어에서 무료 상태가 아니라 제외합니다: %s (%s)', giveaway.title, giveaway.url)
            return None

        return replace(
            giveaway,
            title=data.get('name') or giveaway.title,
            description=(data.get('short_description') or giveaway.description).strip(),
            genres=tuple(genre['description'] for genre in data.get('genres') or [] if genre.get('description')) or giveaway.genres,
            thumbnail_url=data.get('header_image') or giveaway.thumbnail_url,
            original_price=_steam_original_price(price) or giveaway.original_price,
            metacritic=_to_int((data.get('metacritic') or {}).get('score')),
            is_dlc=(data.get('type') or 'game') == 'dlc' or giveaway.is_dlc,
        )
