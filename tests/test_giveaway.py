"""무료 배포 도메인 모델과 수집처 응답 파싱 테스트.

`tests/fixtures/`의 JSON은 실제 API 응답을 그대로 받아 저장한 것이다.
(Steam 응답만 임베드에 쓰는 필드로 줄였다.)
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from conftest import FIXTURE_NOW

from ks_bot.common.giveaway import (
    ClaimKind,
    Giveaway,
    Store,
    clean_title,
    has_desktop_platform,
    strip_promo_sentences,
)
from ks_bot.common.timeutil import Timezone, datetime_now
from ks_bot.core.giveaway import (
    identify_product,
    merge_giveaways,
    parse_epic_payload,
    parse_gamerpower_payload,
    sort_for_display,
)


def make_giveaway(**overrides) -> Giveaway:
    defaults = {
        'store': Store.STEAM,
        'product_id': '214340',
        'title': 'Deponia',
        'url': 'https://store.steampowered.com/app/214340/Deponia/',
    }
    return Giveaway(**{**defaults, **overrides})


class TestStore:
    @pytest.mark.parametrize(
        'url, expected',
        [
            ('https://store.steampowered.com/app/214340/Deponia/', Store.STEAM),
            ('https://store.epicgames.com/p/caravan-sandwitch-05ff58', Store.EPIC),
            ('https://www.gog.com/game/beneath_a_steel_sky', Store.GOG),
            ('https://someone.itch.io/decrypt', Store.ITCH),
            ('https://gaming.amazon.com/loot/xyz', Store.AMAZON),
            ('https://example.com/whatever', Store.OTHER),
            ('', Store.OTHER),
        ],
    )
    def test_from_url(self, url: str, expected: Store):
        assert Store.from_url(url) is expected

    @pytest.mark.parametrize(
        'platforms, expected',
        [
            ('PC, Steam', Store.STEAM),
            ('PC, Epic Games Store', Store.EPIC),
            ('PC, Itch.io, DRM-Free', Store.ITCH),
            ('PC, DRM-Free', Store.OTHER),
            ('Android, iOS', Store.OTHER),
            ('', Store.OTHER),
        ],
    )
    def test_from_platforms(self, platforms: str, expected: Store):
        assert Store.from_platforms(platforms) is expected

    def test_every_store_has_label_and_color(self):
        for store in Store:
            assert store.label
            assert 0 <= store.color <= 0xFFFFFF


class TestCleanTitle:
    @pytest.mark.parametrize(
        'raw, expected',
        [
            ('Deponia (Steam) Giveaway', 'Deponia'),
            ('Caravan SandWitch (Epic Games) Giveaway', 'Caravan SandWitch'),
            ('Dwarven Realms (Steam) Key Giveaway', 'Dwarven Realms'),
            ('Decrypt (Itchio) Giveaway', 'Decrypt'),
            ('Monument Valley', 'Monument Valley'),
        ],
    )
    def test_removes_decoration(self, raw: str, expected: str):
        assert clean_title(raw) == expected


class TestDesktopPlatform:
    @pytest.mark.parametrize(
        'platforms, expected',
        [
            ('PC, Steam', True),
            ('PC, Itch.io, DRM-Free', True),
            ('VR', True),
            ('Android, iOS', False),
            ('iOS', False),
            ('', False),
        ],
    )
    def test_mobile_only_entries_are_rejected(self, platforms: str, expected: bool):
        """모바일 전용 배포는 링크를 따라가도 스토어 앱 안내 페이지로 이어진다."""
        assert has_desktop_platform(platforms) is expected


class TestStripPromoSentences:
    def test_keeps_only_the_game_description(self):
        raw = (
            'Deponia is free on Steam until August 20! '
            'Deponia is a point-and-click game with a unique comic style and challenging puzzles. '
            'Check it out!'
        )
        assert strip_promo_sentences(raw) == 'Deponia is a point-and-click game with a unique comic style and challenging puzzles.'

    def test_drops_leading_hype(self):
        raw = "Trust me, you don't want to miss this journey! Claim Caravan SandWitch for free on the Epic Games Store. It's a cool sci-fi game."
        assert strip_promo_sentences(raw) == "It's a cool sci-fi game."

    def test_all_promo_keeps_original(self):
        """전부 홍보 문장이면 지우는 것보다 남기는 편이 낫다."""
        raw = 'Claim your free game now! Grab it while it lasts!'
        assert strip_promo_sentences(raw) == raw

    def test_plain_description_is_untouched(self):
        raw = 'A 3d first-person survival game set in various locations on Earth.'
        assert strip_promo_sentences(raw) == raw

    def test_empty_input(self):
        assert strip_promo_sentences('') == ''


class TestIdentifyProduct:
    @pytest.mark.parametrize(
        'url, expected',
        [
            ('https://store.steampowered.com/app/214340/Deponia/', (Store.STEAM, '214340')),
            ('https://store.steampowered.com/app/214340/Deponia/?utm_source=x', (Store.STEAM, '214340')),
            ('https://store.epicgames.com/p/caravan-sandwitch-05ff58', (Store.EPIC, 'caravan-sandwitch-05ff58')),
            ('https://www.gog.com/game/beneath_a_steel_sky', (Store.GOG, 'beneath_a_steel_sky')),
        ],
    )
    def test_extracts_stable_identifier(self, url: str, expected: tuple[Store, str]):
        assert identify_product(url) == expected

    def test_unknown_host_falls_back_to_path(self):
        store, product_id = identify_product('https://Example.COM/free/game/')
        assert store is Store.OTHER
        assert product_id == 'example.com/free/game'


class TestGiveawayModel:
    def test_key_uses_store_and_product(self):
        assert make_giveaway().key == 'steam:214340'

    def test_upcoming_and_expired(self):
        now = datetime_now()
        assert make_giveaway(starts_at=now + timedelta(days=1)).is_upcoming is True
        assert make_giveaway(starts_at=now - timedelta(days=1)).is_upcoming is False
        assert make_giveaway(ends_at=now - timedelta(minutes=1)).is_expired is True
        assert make_giveaway(ends_at=now + timedelta(minutes=1)).is_expired is False

    def test_ending_soon(self):
        now = datetime_now()
        assert make_giveaway(ends_at=now + timedelta(hours=3)).is_ending_soon is True
        assert make_giveaway(ends_at=now + timedelta(days=3)).is_ending_soon is False
        # 아직 시작하지 않은 배포는 임박이 아니다.
        assert make_giveaway(starts_at=now + timedelta(days=5), ends_at=now + timedelta(days=5, hours=1)).is_ending_soon is False
        assert make_giveaway().is_ending_soon is False

    def test_merged_with_fills_only_missing_fields(self):
        primary = make_giveaway(title='Deponia', description='한국어 설명')
        secondary = make_giveaway(title='Deponia (Steam)', description='English blurb', original_price='$29.99', metacritic=74)

        merged = primary.merged_with(secondary)

        assert merged.title == 'Deponia'
        assert merged.description == '한국어 설명'
        assert merged.original_price == '$29.99'
        assert merged.metacritic == 74

    def test_merged_with_returns_self_when_nothing_to_fill(self):
        primary = make_giveaway(description='설명', original_price='₩10,500', metacritic=74)
        assert primary.merged_with(make_giveaway()) is primary


class TestEpicParsing:
    @pytest.fixture
    def parsed(self, epic_payload: dict) -> list[Giveaway]:
        return parse_epic_payload(epic_payload, now=FIXTURE_NOW)

    def test_only_actually_free_games_are_parsed(self, parsed: list[Giveaway]):
        """8건 중 실제 무료는 2건뿐이다(진행 중 1 + 예정 1)."""
        assert [item.title for item in parsed] == ['Cardpocalypse Standard Edition', 'Caravan SandWitch']

    def test_discount_promotions_are_not_treated_as_free(self, parsed: list[Giveaway]):
        """`freeGamesPromotions`는 단순 할인 예정(20%, 25%)도 함께 돌려준다."""
        titles = {item.title for item in parsed}
        assert '고스트러너 2' not in titles
        assert 'Monument Valley' not in titles

    def test_finished_promotions_are_excluded(self, parsed: list[Giveaway]):
        titles = {item.title for item in parsed}
        assert titles.isdisjoint({"Them's Fightin' Herds", 'Eternal Threads', 'Castlevania Anniversary Collection'})

    def test_free_addon_with_zero_price_is_excluded(self, parsed: list[Giveaway]):
        """원래 0원인 게임 내 아이템은 알릴 가치가 없다."""
        assert '에픽 메이지 번들' not in {item.title for item in parsed}

    def test_current_promotion_is_active(self, parsed: list[Giveaway]):
        caravan = next(item for item in parsed if item.title == 'Caravan SandWitch')

        assert caravan.starts_at < FIXTURE_NOW < caravan.ends_at
        assert caravan.original_price == '₩32,000'
        assert caravan.description.startswith('매혹적인')
        assert caravan.is_dlc is False
        assert caravan.source == 'epic'

    def test_upcoming_promotion_keeps_start_date(self, parsed: list[Giveaway]):
        cardpocalypse = next(item for item in parsed if item.title.startswith('Cardpocalypse'))
        assert cardpocalypse.starts_at > FIXTURE_NOW

    def test_url_comes_from_mappings_not_product_slug(self, parsed: list[Giveaway]):
        """`productSlug`는 비어 있거나 `.../home` 접미사가 붙어 신뢰할 수 없다."""
        urls = {item.title: item.url for item in parsed}

        assert urls['Caravan SandWitch'] == 'https://store.epicgames.com/p/caravan-sandwitch-05ff58'
        assert urls['Cardpocalypse Standard Edition'] == 'https://store.epicgames.com/p/cardpocalypse'

    def test_images_are_collected(self, parsed: list[Giveaway]):
        assert all(item.thumbnail_url.startswith('http') for item in parsed)

    def test_empty_payload_is_safe(self):
        assert parse_epic_payload({}) == []
        assert parse_epic_payload({'data': {'Catalog': {'searchStore': {'elements': []}}}}) == []


class TestGamerPowerParsing:
    @pytest.fixture
    def parsed(self, gamerpower_payload: list[dict]) -> list[Giveaway]:
        return parse_gamerpower_payload(gamerpower_payload)

    def test_titles_are_cleaned(self, parsed: list[Giveaway]):
        titles = {item.title for item in parsed}
        assert 'Deponia' in titles
        assert 'Dwarven Realms' in titles

    def test_store_is_detected_from_platforms(self, parsed: list[Giveaway]):
        deponia = next(item for item in parsed if item.title == 'Deponia')
        assert deponia.store is Store.STEAM
        assert deponia.original_price == '$29.99'
        assert deponia.ends_at is not None

    def test_key_giveaway_is_marked(self, parsed: list[Giveaway]):
        """키 배포는 스토어 무료와 성격이 다르므로 구분해야 한다."""
        dwarven = next(item for item in parsed if item.title == 'Dwarven Realms')

        assert dwarven.claim_kind is ClaimKind.KEY_DROP
        assert dwarven.ends_at is None  # 원본의 `end_date`가 'N/A'다.

    def test_store_free_is_the_default(self, parsed: list[Giveaway]):
        deponia = next(item for item in parsed if item.title == 'Deponia')
        assert deponia.claim_kind is ClaimKind.STORE_FREE

    def test_mobile_only_giveaways_are_skipped(self, parsed: list[Giveaway]):
        assert 'Beholder: Conductor (Mobile)' not in {item.title for item in parsed}

    def test_description_drops_promotional_sentences(self, parsed: list[Giveaway]):
        deponia = next(item for item in parsed if item.title == 'Deponia')

        assert deponia.description.startswith('Deponia is a point-and-click game')
        assert 'until August 20' not in deponia.description

    def test_url_is_the_redirect_link(self, parsed: list[Giveaway]):
        """이 시점의 URL은 중계 링크다. 실제 스토어 주소는 서비스가 해석한다."""
        deponia = next(item for item in parsed if item.title == 'Deponia')
        assert deponia.url.startswith('https://www.gamerpower.com/open/')

    def test_inactive_entries_are_skipped(self):
        payload = [
            {'id': 1, 'title': 'Old', 'type': 'Game', 'status': 'Expired', 'platforms': 'PC', 'open_giveaway_url': 'https://x/1'},
            {'id': 2, 'title': 'New', 'type': 'Game', 'status': 'Active', 'platforms': 'PC', 'open_giveaway_url': 'https://x/2'},
        ]
        assert [item.title for item in parse_gamerpower_payload(payload)] == ['New']

    def test_non_game_entries_are_skipped(self):
        payload = [{'id': 1, 'title': 'DLC', 'type': 'DLC', 'status': 'Active', 'platforms': 'PC', 'open_giveaway_url': 'https://x/1'}]
        assert parse_gamerpower_payload(payload) == []

    def test_entry_without_url_is_skipped(self):
        assert parse_gamerpower_payload([{'id': 1, 'title': 'X', 'type': 'Game', 'status': 'Active', 'platforms': 'PC'}]) == []

    def test_empty_payload_is_safe(self):
        assert parse_gamerpower_payload([]) == []


class TestMergeAndSort:
    def test_epic_source_wins_over_gamerpower(self):
        epic = make_giveaway(store=Store.EPIC, product_id='caravan', title='Caravan SandWitch', description='한국어', source='epic')
        gamerpower = make_giveaway(
            store=Store.EPIC,
            product_id='caravan',
            title='Caravan SandWitch (Epic Games)',
            description='English',
            original_price='$24.99',
            source='gamerpower',
        )

        merged = merge_giveaways([gamerpower, epic])

        assert len(merged) == 1
        assert merged[0].title == 'Caravan SandWitch'
        assert merged[0].description == '한국어'
        assert merged[0].original_price == '$24.99'  # Epic 쪽에 없던 값만 채운다.

    def test_different_products_are_kept(self):
        items = [make_giveaway(product_id='1'), make_giveaway(product_id='2')]
        assert len(merge_giveaways(items)) == 2

    def test_sort_puts_active_first_then_earliest_deadline(self):
        now = datetime_now()
        upcoming = make_giveaway(product_id='u', title='예정', starts_at=now + timedelta(days=3), ends_at=now + timedelta(days=10))
        late = make_giveaway(product_id='l', title='늦게 마감', ends_at=now + timedelta(days=5))
        soon = make_giveaway(product_id='s', title='곧 마감', ends_at=now + timedelta(hours=2))

        assert [item.title for item in sort_for_display([upcoming, late, soon])] == ['곧 마감', '늦게 마감', '예정']

    def test_sort_handles_missing_deadline(self):
        no_deadline = make_giveaway(product_id='n', title='상시')
        dated = make_giveaway(product_id='d', title='마감 있음', ends_at=datetime_now() + timedelta(days=1))

        assert [item.title for item in sort_for_display([no_deadline, dated])] == ['마감 있음', '상시']


class TestTimestampParsing:
    def test_epic_millisecond_utc_format(self):
        """파이썬 3.10의 fromisoformat은 `Z` 접미사를 이해하지 못한다."""
        from ks_bot.common.timeutil import parse_utc_to_datetime

        parsed = parse_utc_to_datetime('2026-08-13T15:00:00.000Z')

        assert parsed == datetime(2026, 8, 14, 0, 0, tzinfo=Timezone.KST.zone)
