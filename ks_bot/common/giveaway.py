"""무료 배포(giveaway) 도메인 모델.

수집처(Epic 공식 API, GamerPower 등)가 서로 다른 형태로 데이터를 주기 때문에,
정규화된 형태를 여기에 정의하고 각 수집기가 이 타입으로 변환한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import Enum

from ks_bot.common.timeutil import datetime_now

__all__ = ['ClaimKind', 'Giveaway', 'Store', 'clean_title', 'has_desktop_platform', 'strip_promo_sentences']

# 마감이 이 시간 안으로 들어오면 "임박"으로 표시한다.
ENDING_SOON_THRESHOLD = timedelta(hours=24)


class Store(Enum):
    """배포가 이루어지는 스토어."""

    STEAM = 'steam'
    EPIC = 'epic'
    GOG = 'gog'
    ITCH = 'itch'
    UBISOFT = 'ubisoft'
    AMAZON = 'amazon'
    ORIGIN = 'origin'
    MICROSOFT = 'microsoft'
    OTHER = 'other'

    @property
    def label(self) -> str:
        return _STORE_LABELS[self]

    @property
    def color(self) -> int:
        """임베드 좌측 바 색상. 스크롤하며 스토어를 구분하는 용도다."""
        return _STORE_COLORS[self]

    @classmethod
    def from_url(cls, url: str) -> Store:
        """스토어 URL의 호스트로 스토어를 판별한다."""
        lowered = (url or '').lower()
        for store, patterns in _STORE_URL_PATTERNS:
            if any(pattern in lowered for pattern in patterns):
                return store
        return cls.OTHER

    @classmethod
    def from_platforms(cls, platforms: str) -> Store:
        """GamerPower의 `platforms` 문자열(`'PC, Epic Games Store'`)로 스토어를 판별한다."""
        lowered = (platforms or '').lower()
        for store, keywords in _STORE_PLATFORM_KEYWORDS:
            if any(keyword in lowered for keyword in keywords):
                return store
        return cls.OTHER


_STORE_LABELS: dict[Store, str] = {
    Store.STEAM: 'Steam',
    Store.EPIC: 'Epic Games',
    Store.GOG: 'GOG',
    Store.ITCH: 'itch.io',
    Store.UBISOFT: 'Ubisoft',
    Store.AMAZON: 'Prime Gaming',
    Store.ORIGIN: 'EA',
    Store.MICROSOFT: 'Microsoft',
    Store.OTHER: '기타',
}

_STORE_COLORS: dict[Store, int] = {
    Store.STEAM: 0x66C0F4,
    Store.EPIC: 0x313131,
    Store.GOG: 0xA05EB5,
    Store.ITCH: 0xFA5C5C,
    Store.UBISOFT: 0x0F72C4,
    Store.AMAZON: 0xFF9900,
    Store.ORIGIN: 0xFF4747,
    Store.MICROSOFT: 0x107C10,
    Store.OTHER: 0x5865F2,
}

# 앞에 오는 항목부터 검사한다. 더 구체적인 패턴이 먼저 와야 한다.
_STORE_URL_PATTERNS: tuple[tuple[Store, tuple[str, ...]], ...] = (
    (Store.STEAM, ('store.steampowered.com', 'steamcommunity.com')),
    (Store.EPIC, ('epicgames.com',)),
    (Store.GOG, ('gog.com',)),
    (Store.ITCH, ('itch.io',)),
    (Store.UBISOFT, ('ubisoft.com', 'ubi.com')),
    (Store.AMAZON, ('gaming.amazon.com',)),
    (Store.ORIGIN, ('origin.com', 'ea.com')),
    (Store.MICROSOFT, ('microsoft.com', 'xbox.com')),
)

_STORE_PLATFORM_KEYWORDS: tuple[tuple[Store, tuple[str, ...]], ...] = (
    (Store.STEAM, ('steam',)),
    (Store.EPIC, ('epic',)),
    (Store.GOG, ('gog',)),
    (Store.ITCH, ('itch',)),
    (Store.UBISOFT, ('ubisoft',)),
    (Store.AMAZON, ('amazon', 'prime')),
    (Store.ORIGIN, ('origin', 'ea app', 'ea play')),
    (Store.MICROSOFT, ('xbox', 'microsoft')),
)


class ClaimKind(Enum):
    """무료로 받는 방식.

    스토어 자체가 무료로 풀린 것과, 수량이 정해진 키를 나눠주는 것은 성격이 완전히 다르다.
    후자는 재고가 떨어지면 링크만 남으므로 사용자에게 구분해서 알려줘야 한다.
    """

    STORE_FREE = 'store_free'
    KEY_DROP = 'key_drop'


@dataclass(frozen=True)
class Giveaway:
    """정규화된 무료 배포 항목."""

    store: Store
    product_id: str
    title: str
    url: str
    claim_kind: ClaimKind = ClaimKind.STORE_FREE
    description: str = ''
    genres: tuple[str, ...] = ()
    original_price: str = ''
    thumbnail_url: str = ''
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_dlc: bool = False
    metacritic: int = 0
    source: str = ''
    extra_urls: tuple[str, ...] = field(default_factory=tuple)

    @property
    def key(self) -> str:
        """중복 발행 판정에 쓰는 안정적인 키.

        URL 전체를 쓰면 추적 파라미터나 로케일 접미사가 붙는 순간 깨지므로,
        스토어와 상품 식별자만으로 만든다.
        """
        return f'{self.store.value}:{self.product_id}'

    @property
    def is_upcoming(self) -> bool:
        """아직 시작하지 않은 예정 배포인지."""
        return self.starts_at is not None and self.starts_at > datetime_now()

    @property
    def is_expired(self) -> bool:
        return self.ends_at is not None and self.ends_at <= datetime_now()

    @property
    def is_ending_soon(self) -> bool:
        if self.ends_at is None or self.is_upcoming:
            return False
        return self.ends_at - datetime_now() <= ENDING_SOON_THRESHOLD

    def merged_with(self, other: Giveaway) -> Giveaway:
        """같은 상품에 대한 다른 수집처의 정보를 병합한다.

        `self`의 값을 우선하고, 비어 있는 항목만 `other`에서 채운다.
        """
        updates = {
            name: getattr(other, name)
            for name in ('description', 'original_price', 'thumbnail_url', 'starts_at', 'ends_at', 'metacritic')
            if not getattr(self, name) and getattr(other, name)
        }
        if not self.genres and other.genres:
            updates['genres'] = other.genres
        return replace(self, **updates) if updates else self


_TITLE_NOISE = re.compile(
    r'\s*(\((?:steam|epic games?|gog|itch\.?io|ubisoft|origin|ea|drm-free|pc)\)|'
    r'(?:steam\s+)?key\s+giveaway|giveaway|free\s+download)\s*',
    re.IGNORECASE,
)


def clean_title(raw_title: str) -> str:
    """수집처가 붙인 장식 문구를 제거한다.

    GamerPower는 `'Deponia (Steam) Giveaway'`처럼 스토어명과 `Giveaway`를 덧붙인다.
    """
    cleaned = _TITLE_NOISE.sub(' ', raw_title or '')
    return re.sub(r'\s{2,}', ' ', cleaned).strip(' -–—:|')


# 게임 설명이 아니라 "지금 받으세요" 류의 홍보 문장을 걸러내기 위한 표지.
_PROMO_SENTENCE = re.compile(
    r'\b(giveaway|for free|free (?:on|via|until|for|to)|claim|check it out|'
    r"give it a try|don'?t (?:want to )?miss|grab (?:it|your|this)|please note|"
    r'hurry|limited time|while (?:it|they) last)\b',
    re.IGNORECASE,
)
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')


def strip_promo_sentences(description: str) -> str:
    """설명에서 홍보 문장을 걷어내고 게임 소개만 남긴다.

    수집처의 설명은 보통 `"Deponia is free on Steam until August 20! Deponia is a
    point-and-click game... Check it out!"`처럼 홍보 문장과 소개가 섞여 있다.
    임베드에는 이미 가격과 마감이 따로 표시되므로 홍보 문장은 자리만 차지한다.

    남는 문장이 없으면 원문을 그대로 돌려준다(정보를 통째로 잃는 것보다 낫다).
    """
    text = (description or '').strip()
    if not text:
        return ''

    kept = [sentence for sentence in _SENTENCE_SPLIT.split(text) if sentence.strip() and not _PROMO_SENTENCE.search(sentence)]
    return ' '.join(kept).strip() or text


def has_desktop_platform(platforms: str) -> bool:
    """PC(또는 PC 스토어)에서 받을 수 있는 배포인지.

    GamerPower는 모바일 전용 배포도 함께 내려준다. 이런 항목은 링크를 따라가도
    스토어 앱 안내 페이지로 이어져 상품을 특정할 수 없다.
    """
    lowered = (platforms or '').lower()
    if not lowered:
        return False
    return any(keyword in lowered for keyword in _DESKTOP_PLATFORM_KEYWORDS)


_DESKTOP_PLATFORM_KEYWORDS = (
    'pc',
    'steam',
    'epic',
    'gog',
    'itch',
    'ubisoft',
    'origin',
    'ea app',
    'ea play',
    'drm-free',
    'battle.net',
    'microsoft',
    'xbox',
    'vr',
)
