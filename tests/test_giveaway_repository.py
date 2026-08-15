"""무료 배포 발행 이력 저장소 테스트."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

from test_giveaway import make_giveaway

from ks_bot.common.giveaway import ClaimKind, Giveaway, Store
from ks_bot.common.timeutil import datetime_now
from ks_bot.core.giveaway_repository import GiveawayRepository


class TestFilterUnannounced:
    async def test_unknown_giveaway_is_new(self, giveaway_repository: GiveawayRepository):
        assert await giveaway_repository.filter_unannounced([make_giveaway()]) == [make_giveaway()]

    async def test_announced_giveaway_is_not_repeated(self, giveaway_repository: GiveawayRepository):
        giveaway = make_giveaway(ends_at=datetime_now() + timedelta(days=3))
        await giveaway_repository.mark_announced(giveaway)

        assert await giveaway_repository.filter_unannounced([giveaway]) == []

    async def test_minor_deadline_correction_does_not_repeat(self, giveaway_repository: GiveawayRepository):
        """수집처가 마감을 몇 시간 단위로 정정하는 일은 흔하다. 그때마다 다시 알리면 안 된다."""
        ends_at = datetime_now() + timedelta(days=3)
        await giveaway_repository.mark_announced(make_giveaway(ends_at=ends_at))

        corrected = make_giveaway(ends_at=ends_at + timedelta(hours=5))
        assert await giveaway_repository.filter_unannounced([corrected]) == []

    async def test_redistribution_is_announced_again(self, giveaway_repository: GiveawayRepository):
        """같은 게임이 한참 뒤에 다시 풀리면 새 배포로 봐야 한다."""
        await giveaway_repository.mark_announced(make_giveaway(ends_at=datetime_now() + timedelta(days=1)))

        redistributed = make_giveaway(ends_at=datetime_now() + timedelta(days=200))
        assert len(await giveaway_repository.filter_unannounced([redistributed])) == 1

    async def test_upcoming_and_active_are_announced_separately(self, giveaway_repository: GiveawayRepository):
        """예정 배포를 알린 뒤, 실제로 시작하면 한 번 더 알려야 한다."""
        now = datetime_now()
        upcoming = make_giveaway(starts_at=now + timedelta(days=3), ends_at=now + timedelta(days=10))
        await giveaway_repository.mark_announced(upcoming)

        assert await giveaway_repository.filter_unannounced([upcoming]) == []

        started = replace(upcoming, starts_at=now - timedelta(minutes=1))
        assert await giveaway_repository.filter_unannounced([started]) == [started]

    async def test_empty_input(self, giveaway_repository: GiveawayRepository):
        assert await giveaway_repository.filter_unannounced([]) == []


class TestMarkAnnounced:
    async def test_is_empty_flips_after_first_record(self, giveaway_repository: GiveawayRepository):
        assert await giveaway_repository.is_empty() is True

        await giveaway_repository.mark_announced(make_giveaway())

        assert await giveaway_repository.is_empty() is False
        assert await giveaway_repository.count() == 1

    async def test_marking_twice_updates_in_place(self, giveaway_repository: GiveawayRepository):
        giveaway = make_giveaway()
        await giveaway_repository.mark_announced(giveaway, message_id=1)
        await giveaway_repository.mark_announced(giveaway, message_id=2)

        assert await giveaway_repository.count() == 1

    async def test_mark_all(self, giveaway_repository: GiveawayRepository):
        await giveaway_repository.mark_all_announced([make_giveaway(product_id='1'), make_giveaway(product_id='2')])
        assert await giveaway_repository.count() == 2


class TestListActive:
    async def test_round_trips_every_field(self, giveaway_repository: GiveawayRepository):
        original = Giveaway(
            store=Store.STEAM,
            product_id='214340',
            title='Deponia',
            url='https://store.steampowered.com/app/214340/Deponia/',
            claim_kind=ClaimKind.KEY_DROP,
            description='설명',
            genres=('어드벤처', '인디'),
            original_price='₩ 10,500',
            thumbnail_url='https://img/header.jpg',
            ends_at=datetime_now() + timedelta(days=2),
            is_dlc=False,
            metacritic=74,
            source='gamerpower',
            extra_urls=('https://www.gamerpower.com/open/deponia-steam-giveaway',),
        )
        await giveaway_repository.mark_announced(original)

        assert await giveaway_repository.list_active() == [original]

    async def test_expired_entries_are_hidden(self, giveaway_repository: GiveawayRepository):
        await giveaway_repository.mark_announced(make_giveaway(product_id='old', ends_at=datetime_now() - timedelta(days=1)))
        await giveaway_repository.mark_announced(make_giveaway(product_id='live', ends_at=datetime_now() + timedelta(days=1)))

        assert [item.product_id for item in await giveaway_repository.list_active()] == ['live']

    async def test_upcoming_entries_are_hidden(self, giveaway_repository: GiveawayRepository):
        now = datetime_now()
        await giveaway_repository.mark_announced(make_giveaway(product_id='soon', starts_at=now + timedelta(days=2), ends_at=now + timedelta(days=9)))

        assert await giveaway_repository.list_active() == []

    async def test_sorted_by_deadline_with_undated_last(self, giveaway_repository: GiveawayRepository):
        now = datetime_now()
        await giveaway_repository.mark_announced(make_giveaway(product_id='undated', title='상시'))
        await giveaway_repository.mark_announced(make_giveaway(product_id='late', title='늦게', ends_at=now + timedelta(days=5)))
        await giveaway_repository.mark_announced(make_giveaway(product_id='soon', title='곧', ends_at=now + timedelta(hours=3)))

        assert [item.title for item in await giveaway_repository.list_active()] == ['곧', '늦게', '상시']

    async def test_corrupted_payload_is_skipped(self, giveaway_repository: GiveawayRepository):
        await giveaway_repository.mark_announced(make_giveaway())
        await giveaway_repository._execute("UPDATE giveaways SET payload = 'not json'")

        assert await giveaway_repository.list_active() == []


class TestUrlCache:
    async def test_cache_round_trip(self, giveaway_repository: GiveawayRepository):
        assert await giveaway_repository.get_cached_url('https://gp/open/x') is None

        await giveaway_repository.cache_url('https://gp/open/x', 'https://store.steampowered.com/app/1/X/')

        assert await giveaway_repository.get_cached_url('https://gp/open/x') == 'https://store.steampowered.com/app/1/X/'

    async def test_cache_is_updated(self, giveaway_repository: GiveawayRepository):
        await giveaway_repository.cache_url('https://gp/open/x', 'https://old/')
        await giveaway_repository.cache_url('https://gp/open/x', 'https://new/')

        assert await giveaway_repository.get_cached_url('https://gp/open/x') == 'https://new/'


class TestPurge:
    async def test_only_long_expired_records_are_removed(self, giveaway_repository: GiveawayRepository):
        now = datetime_now()
        await giveaway_repository.mark_announced(make_giveaway(product_id='ancient', ends_at=now - timedelta(days=60)))
        await giveaway_repository.mark_announced(make_giveaway(product_id='recent', ends_at=now - timedelta(days=2)))
        await giveaway_repository.mark_announced(make_giveaway(product_id='undated'))

        assert await giveaway_repository.purge_expired() == 1
        assert await giveaway_repository.count() == 2

    async def test_recently_expired_records_still_block_reannouncement(self, giveaway_repository: GiveawayRepository):
        """정리 주기가 너무 짧으면 방금 끝난 배포가 다시 올라온다."""
        expired = make_giveaway(ends_at=datetime_now() - timedelta(days=2))
        await giveaway_repository.mark_announced(expired)
        await giveaway_repository.purge_expired()

        assert await giveaway_repository.filter_unannounced([expired]) == []
