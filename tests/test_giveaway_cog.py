"""무료 배포 코그의 발행 형태와 발행 로직 테스트.

디스코드 게이트웨이에 연결하지 않고, 임베드 구성과 발행 흐름만 검증한다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import discord
import pytest
from test_giveaway import make_giveaway

from ks_bot.cogs.giveaway import (
    MAX_ANNOUNCE_PER_RUN,
    MAX_EMBEDS_PER_MESSAGE,
    GiveawayCog,
    GiveawayLinkView,
    build_giveaway_embed,
    build_group_header,
    build_list_embed,
    format_timestamp,
    group_for_announcement,
)
from ks_bot.common.giveaway import ClaimKind, Store
from ks_bot.common.timeutil import datetime_now
from ks_bot.config import Settings

CHANNEL_ID = 999
ROLE_ID = 555


class FakeMessage:
    def __init__(self, message_id: int):
        self.id = message_id


class FakeChannel:
    def __init__(self, fail_on: set[int] | None = None):
        self.sent: list[SimpleNamespace] = []
        self.fail_on = fail_on or set()
        self.attempts = 0

    async def send(self, content=None, embed=None, embeds=None, view=None) -> FakeMessage:
        # 실패한 전송은 `sent`에 쌓이지 않으므로, 시도 횟수를 따로 센다.
        attempt = self.attempts
        self.attempts += 1
        if attempt in self.fail_on:
            raise discord.HTTPException(SimpleNamespace(status=500, reason='서버 오류'), '전송 실패')
        payload = list(embeds or ([embed] if embed is not None else []))
        self.sent.append(SimpleNamespace(content=content, embeds=payload, view=view))
        return FakeMessage(attempt + 1)

    @property
    def embeds(self) -> list[discord.Embed]:
        """전송된 모든 메시지의 임베드를 순서대로 펼친다."""
        return [embed for message in self.sent for embed in message.embeds]


def field_value(embed: discord.Embed, name_fragment: str) -> str:
    return next(field.value for field in embed.fields if name_fragment in field.name)


def has_field(embed: discord.Embed, name_fragment: str) -> bool:
    return any(name_fragment in field.name for field in embed.fields)


class TestGiveawayEmbed:
    def test_basic_layout(self):
        giveaway = make_giveaway(
            title='Deponia',
            description='세계가 거대한 쓰레기장으로 변해 버린 데포니아.',
            genres=('어드벤처', '인디'),
            original_price='₩ 10,500',
            thumbnail_url='https://img/header.jpg',
            metacritic=74,
            source='gamerpower',
            ends_at=datetime_now() + timedelta(days=3),
        )

        embed = build_giveaway_embed(giveaway)

        assert embed.title == 'Deponia'
        assert embed.url == giveaway.url
        assert embed.color.value == Store.STEAM.color
        assert embed.author.name == '🎁 무료 배포 · Steam'
        assert '*어드벤처 · 인디*' in embed.description
        assert '데포니아' in embed.description
        assert embed.image.url == 'https://img/header.jpg'
        assert '메타크리틱 74' in embed.footer.text
        assert '출처 GamerPower' in embed.footer.text

    def test_price_shows_strikethrough_original(self):
        embed = build_giveaway_embed(make_giveaway(original_price='₩ 10,500'))
        assert field_value(embed, '가격') == '~~₩ 10,500~~ → **무료**'

    def test_price_without_original(self):
        assert field_value(build_giveaway_embed(make_giveaway()), '가격') == '**무료**'

    def test_deadline_uses_discord_timestamps(self):
        """UTC 문자열을 박아두면 아무도 읽지 않는다. 각자 시간대로 렌더되게 한다."""
        ends_at = datetime_now() + timedelta(days=3)
        value = field_value(build_giveaway_embed(make_giveaway(ends_at=ends_at)), '마감')

        assert format_timestamp(ends_at) in value
        assert format_timestamp(ends_at, 'R') in value

    def test_missing_deadline_is_stated(self):
        assert field_value(build_giveaway_embed(make_giveaway()), '마감') == '미정'

    def test_ending_soon_is_highlighted(self):
        embed = build_giveaway_embed(make_giveaway(ends_at=datetime_now() + timedelta(hours=5)))
        assert embed.author.name.startswith('🔥 마감 임박')

    def test_compact_card_drops_the_redundant_status(self):
        """묶어 보낼 때는 머리말이 상태를 말해주므로 카드마다 반복할 필요가 없다."""
        embed = build_giveaway_embed(make_giveaway(ends_at=datetime_now() + timedelta(days=3)), compact=True)
        assert embed.author.name == 'Steam'

    def test_compact_card_still_warns_about_deadlines(self):
        embed = build_giveaway_embed(make_giveaway(ends_at=datetime_now() + timedelta(hours=5)), compact=True)
        assert embed.author.name == '🔥 마감 임박 · Steam'

    def test_upcoming_shows_start_instead_of_deadline(self):
        now = datetime_now()
        giveaway = make_giveaway(starts_at=now + timedelta(days=4), ends_at=now + timedelta(days=11))

        embed = build_giveaway_embed(giveaway)

        assert embed.author.name.startswith('🗓️ 배포 예정')
        assert format_timestamp(giveaway.starts_at) in field_value(embed, '시작')
        assert not has_field(embed, '마감')

    def test_key_drop_is_explained(self):
        """선착순 키 배포는 마감 전에 끝날 수 있어 별도로 알려야 한다."""
        embed = build_giveaway_embed(make_giveaway(claim_kind=ClaimKind.KEY_DROP))
        assert '소진' in field_value(embed, '받는 방법')

    def test_store_free_has_no_claim_note(self):
        assert not has_field(build_giveaway_embed(make_giveaway()), '받는 방법')

    def test_store_determines_color(self):
        embed = build_giveaway_embed(make_giveaway(store=Store.EPIC, url='https://store.epicgames.com/p/x'))
        assert embed.color.value == Store.EPIC.color
        assert embed.author.name.endswith('Epic Games')

    def test_long_text_is_truncated(self):
        embed = build_giveaway_embed(make_giveaway(title='가' * 400, description='나' * 5000))

        assert len(embed.title) <= 256
        assert len(embed.description) <= 4096


class TestLinkView:
    def test_button_points_at_the_store(self):
        giveaway = make_giveaway()
        button = GiveawayLinkView([giveaway]).children[0]

        assert button.url == giveaway.url
        assert button.label == 'Steam에서 받기'
        assert button.style is discord.ButtonStyle.link

    def test_key_drop_uses_a_neutral_label(self):
        """키 배포는 스토어가 아니라 배포 사이트로 가는 경우가 많다."""
        giveaway = make_giveaway(claim_kind=ClaimKind.KEY_DROP, url='https://www.alienwarearena.com/giveaway/x')
        assert GiveawayLinkView([giveaway]).children[0].label == '받으러 가기'

    def test_grouped_buttons_are_named_after_the_game(self):
        """여러 개가 나란히 놓이면 어느 게임의 버튼인지가 가장 중요하다."""
        items = [make_giveaway(product_id='1', title='첫 게임'), make_giveaway(product_id='2', title='둘째 게임')]

        assert [button.label for button in GiveawayLinkView(items).children] == ['첫 게임', '둘째 게임']


class TestListEmbed:
    def test_lists_every_giveaway(self):
        items = [make_giveaway(product_id='1', title='첫 번째'), make_giveaway(product_id='2', title='두 번째')]

        embed = build_list_embed(items)

        assert '2건' in embed.description
        assert [field.name for field in embed.fields] == ['첫 번째 (Steam)', '두 번째 (Steam)']

    def test_key_drop_is_flagged(self):
        embed = build_list_embed([make_giveaway(claim_kind=ClaimKind.KEY_DROP)])
        assert '선착순 키' in embed.fields[0].value

    def test_field_limit_is_respected(self):
        items = [make_giveaway(product_id=str(index)) for index in range(30)]
        assert len(build_list_embed(items).fields) == 25


@pytest.fixture
def giveaway_settings(settings: Settings) -> Settings:
    return replace(settings, giveaway_channel_id=CHANNEL_ID, giveaway_mention_role_id=ROLE_ID)


@pytest.fixture
async def cog(giveaway_settings: Settings) -> AsyncIterator[GiveawayCog]:
    channel = FakeChannel()
    bot = SimpleNamespace(settings=giveaway_settings, guilds=[], get_channel=lambda channel_id: channel if channel_id == CHANNEL_ID else None)
    instance = GiveawayCog(bot)
    instance.channel = channel  # 테스트에서 꺼내 쓰기 위한 참조
    await instance.service.connect()
    try:
        yield instance
    finally:
        await instance.service.aclose()


class TestGrouping:
    def test_active_and_upcoming_are_separated(self):
        now = datetime_now()
        active = make_giveaway(product_id='a', title='지금', ends_at=now + timedelta(days=2))
        upcoming = make_giveaway(product_id='u', title='나중', starts_at=now + timedelta(days=3), ends_at=now + timedelta(days=10))

        groups = group_for_announcement([upcoming, active])

        assert [label for label, _ in groups] == ['🎁 지금 무료로 받을 수 있어요', '🗓️ 곧 무료로 풀립니다']
        assert [item.title for _, items in groups for item in items] == ['지금', '나중']

    def test_empty_groups_are_dropped(self):
        groups = group_for_announcement([make_giveaway()])
        assert len(groups) == 1

    def test_same_store_items_stay_together(self):
        items = [
            make_giveaway(product_id='1', store=Store.STEAM, title='S1'),
            make_giveaway(product_id='2', store=Store.EPIC, title='E1'),
            make_giveaway(product_id='3', store=Store.STEAM, title='S2'),
        ]

        _, group = group_for_announcement(items)[0]

        assert [item.store for item in group] == [Store.EPIC, Store.STEAM, Store.STEAM]

    def test_message_embed_limit_is_respected(self):
        """디스코드는 한 메시지에 임베드를 10개까지만 허용한다."""
        items = [make_giveaway(product_id=str(index)) for index in range(MAX_EMBEDS_PER_MESSAGE + 3)]

        groups = group_for_announcement(items)

        assert [len(group) for _, group in groups] == [MAX_EMBEDS_PER_MESSAGE, 3]

    def test_header_lists_stores(self):
        items = [make_giveaway(product_id='1', store=Store.STEAM), make_giveaway(product_id='2', store=Store.EPIC)]

        header = build_group_header('🎁 지금 무료로 받을 수 있어요', items, mention='<@&5>')

        assert header.startswith('<@&5>')
        assert '2건' in header
        assert 'Epic Games, Steam' in header


class TestAnnounce:
    async def test_everything_fits_in_one_message(self, cog: GiveawayCog):
        """건마다 메시지를 나누면 채널이 시끄러워진다."""
        items = [make_giveaway(product_id=str(index)) for index in range(3)]

        assert await cog.announce(cog.channel, items) == 3

        assert len(cog.channel.sent) == 1
        assert len(cog.channel.sent[0].embeds) == 3
        assert len(cog.channel.sent[0].view.children) == 3

    async def test_mention_appears_once(self, cog: GiveawayCog):
        now = datetime_now()
        items = [
            make_giveaway(product_id='a', ends_at=now + timedelta(days=2)),
            make_giveaway(product_id='u', starts_at=now + timedelta(days=3), ends_at=now + timedelta(days=9)),
        ]

        await cog.announce(cog.channel, items)

        contents = [message.content for message in cog.channel.sent]
        assert len(contents) == 2
        assert contents[0].startswith(f'<@&{ROLE_ID}>')
        assert f'<@&{ROLE_ID}>' not in contents[1]

    async def test_grouped_cards_use_thumbnails(self, cog: GiveawayCog):
        """묶어 보낼 때 큰 이미지를 쓰면 메시지가 지나치게 길어진다."""
        items = [make_giveaway(product_id=str(index), thumbnail_url='https://img/x.jpg') for index in range(2)]

        await cog.announce(cog.channel, items)

        embed = cog.channel.embeds[0]
        assert embed.thumbnail.url == 'https://img/x.jpg'
        assert embed.image.url is None

    async def test_single_card_keeps_the_large_image(self, cog: GiveawayCog):
        await cog.announce(cog.channel, [make_giveaway(thumbnail_url='https://img/x.jpg')])

        embed = cog.channel.embeds[0]
        assert embed.image.url == 'https://img/x.jpg'
        assert embed.thumbnail.url is None

    async def test_buttons_follow_the_embed_order(self, cog: GiveawayCog):
        """버튼과 카드 순서가 어긋나면 어느 게임의 버튼인지 알 수 없다."""
        now = datetime_now()
        items = [
            make_giveaway(product_id='1', title='늦게 마감', ends_at=now + timedelta(days=5)),
            make_giveaway(product_id='2', title='곧 마감', ends_at=now + timedelta(hours=6)),
        ]

        await cog.announce(cog.channel, items)

        message = cog.channel.sent[0]
        assert [button.label for button in message.view.children] == ['곧 마감', '늦게 마감']
        assert [embed.title for embed in message.embeds] == ['곧 마감', '늦게 마감']

    async def test_announcement_is_recorded(self, cog: GiveawayCog):
        giveaway = make_giveaway()
        await cog.announce(cog.channel, [giveaway])

        assert await cog.service.repository.filter_unannounced([giveaway]) == []

    async def test_failed_send_is_not_recorded(self, cog: GiveawayCog):
        """기록을 남기면 다음 주기에 재시도되지 않는다."""
        cog.channel.fail_on = {0}
        giveaway = make_giveaway()

        assert await cog.announce(cog.channel, [giveaway]) == 0
        assert await cog.service.repository.filter_unannounced([giveaway]) == [giveaway]

    async def test_one_failing_group_does_not_stop_the_rest(self, cog: GiveawayCog):
        cog.channel.fail_on = {0}  # 진행 중 묶음만 실패시킨다.
        now = datetime_now()
        items = [
            make_giveaway(product_id='a', ends_at=now + timedelta(days=2)),
            make_giveaway(product_id='u', starts_at=now + timedelta(days=3), ends_at=now + timedelta(days=9)),
        ]

        assert await cog.announce(cog.channel, items) == 1
        # 실패한 묶음은 기록되지 않아 다음 주기에 다시 대상이 된다.
        assert [item.product_id for item in await cog.service.repository.filter_unannounced(items)] == ['a']

    async def test_batch_is_capped(self, cog: GiveawayCog):
        items = [make_giveaway(product_id=str(index)) for index in range(MAX_ANNOUNCE_PER_RUN + 5)]

        announced = await cog.announce(cog.channel, items)

        assert announced == MAX_ANNOUNCE_PER_RUN
        # 발행하지 못한 항목은 기록되지 않아 다음 주기에 다시 대상이 된다.
        assert len(await cog.service.repository.filter_unannounced(items)) == 5

    async def test_no_mention_configured(self, settings: Settings):
        bot = SimpleNamespace(settings=replace(settings, giveaway_channel_id=CHANNEL_ID), guilds=[], get_channel=lambda _: None)
        instance = GiveawayCog(bot)
        await instance.service.connect()
        channel = FakeChannel()
        try:
            await instance.announce(channel, [make_giveaway()])
            assert not channel.sent[0].content.startswith('<@&')
        finally:
            await instance.service.aclose()


class TestPollingLoop:
    async def _run_once(self, cog: GiveawayCog) -> None:
        await GiveawayCog.check_giveaways.coro(cog)

    async def test_first_run_seeds_without_flooding_the_channel(self, cog: GiveawayCog, monkeypatch):
        """봇을 처음 켠 시점에 이미 진행 중이던 배포를 한꺼번에 쏟아내면 안 된다."""
        items = [make_giveaway(product_id=str(index)) for index in range(4)]
        monkeypatch.setattr(cog.service, 'find_new', lambda: _returns(items))

        await self._run_once(cog)

        assert cog.channel.sent == []
        assert await cog.service.repository.count() == 4

    async def test_second_run_announces(self, cog: GiveawayCog, monkeypatch):
        monkeypatch.setattr(cog.service, 'find_new', lambda: _returns([make_giveaway(product_id='seed')]))
        await self._run_once(cog)

        monkeypatch.setattr(cog.service, 'find_new', lambda: _returns([make_giveaway(product_id='new')]))
        await self._run_once(cog)

        assert len(cog.channel.embeds) == 1

    async def test_nothing_new_sends_nothing(self, cog: GiveawayCog, monkeypatch):
        monkeypatch.setattr(cog.service, 'find_new', lambda: _returns([]))

        await self._run_once(cog)

        assert cog.channel.sent == []

    async def test_missing_channel_is_reported_not_crashed(self, cog: GiveawayCog, monkeypatch):
        monkeypatch.setattr(cog.bot, 'get_channel', lambda _: None)
        monkeypatch.setattr(cog.service, 'find_new', lambda: _returns([make_giveaway()]))

        await self._run_once(cog)

        assert cog.channel.sent == []


async def _returns(value):
    return value
