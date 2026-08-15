"""코그의 순수 로직(입력 파싱, 상태 관리) 테스트.

디스코드 게이트웨이에 연결하지 않고 검증할 수 있는 부분만 다룬다.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from factories import make_player, make_player_payload
from ks_bot.cogs.balancer import (
    PUBG_APP_NAME,
    SCORE_TIERS,
    Balancer,
    build_score_embed,
    is_playing_pubg,
    parse_discord_mention,
    parse_player_name_from_display_name,
    parse_pubg_account_id,
)
from ks_bot.cogs.game import RPS_CHOICES, judge_rps, safe_file_name
from ks_bot.cogs.music import GuildPlayer, Track
from ks_bot.common.errors import PlayerNotFoundError
from ks_bot.core.youtube import TrackInfo


def fake_member(display_name: str = '테스터', *, playing: bool = False, party_id: str | None = None, member_id: int = 1):
    activity = SimpleNamespace(name=PUBG_APP_NAME if playing else 'Visual Studio Code', party={'id': party_id} if party_id else None)
    return SimpleNamespace(id=member_id, display_name=display_name, activities=(activity,))


def fake_context(author, members: dict[int, object] | None = None):
    members = members or {}
    return SimpleNamespace(author=author, guild=SimpleNamespace(get_member=members.get))


class TestMentionParsing:
    @pytest.mark.parametrize(
        'value, expected',
        [
            ('<@1234567890>', 1234567890),
            ('<@!1234567890>', 1234567890),
            (' <@1234567890> ', 1234567890),
            ('SonPANG', None),
            ('', None),
            ('<@abc>', None),
        ],
    )
    def test_parse_discord_mention(self, value: str, expected: int | None):
        assert parse_discord_mention(value) == expected


class TestDisplayNameParsing:
    @pytest.mark.parametrize(
        'display_name, expected',
        [
            ('손팽 | SonPANG', 'SonPANG'),
            ('손팽|SonPANG', 'SonPANG'),
            ('SonPANG', 'SonPANG'),  # 구분자가 없으면 그대로 사용한다(예전에는 IndexError).
            ('  SonPANG  ', 'SonPANG'),
        ],
    )
    def test_parse_player_name_from_display_name(self, display_name: str, expected: str):
        assert parse_player_name_from_display_name(display_name) == expected


class TestActivityParsing:
    def test_account_id_from_party(self):
        member = fake_member(playing=True, party_id='abc123-def456')
        assert parse_pubg_account_id(member) == 'abc123'
        assert is_playing_pubg(member) is True

    def test_not_playing_returns_none(self):
        member = fake_member(playing=False)
        assert parse_pubg_account_id(member) is None
        assert is_playing_pubg(member) is False

    def test_playing_without_party_returns_none(self):
        assert parse_pubg_account_id(fake_member(playing=True)) is None

    def test_member_without_activities(self):
        assert parse_pubg_account_id(SimpleNamespace(activities=None)) is None


class TestScoreEmbed:
    @pytest.mark.parametrize(
        'score, expected_keyword',
        [
            (10.0, '애송이'),
            (40.0, '좀 치는'),
            (60.0, '조심'),
            (80.0, '스카우터'),
            (0.0, '애송이'),
        ],
    )
    def test_tier_selection(self, score: float, expected_keyword: str):
        embed = build_score_embed('SonPANG', score)
        assert expected_keyword in embed.title
        assert 'SonPANG' in embed.description
        assert f'{score:.1f}' in embed.description

    def test_tiers_are_sorted_descending(self):
        thresholds = [tier.min_score for tier in SCORE_TIERS]
        assert thresholds == sorted(thresholds, reverse=True)


@pytest.fixture
async def balancer_cog(settings) -> AsyncIterator[Balancer]:
    """디스코드 연결 없이 밸런서 코그만 만들어 사용한다."""
    cog = Balancer(SimpleNamespace(settings=settings, guilds=[]))
    await cog.balancer.connect()
    try:
        yield cog
    finally:
        await cog.balancer.aclose()


class TestBalancerResolution:
    async def test_linked_account_wins(self, balancer_cog: Balancer):
        await balancer_cog.balancer.repository.upsert_player(make_player('LinkedPlayer'))
        await balancer_cog.balancer.link_discord_account('LinkedPlayer', 42)

        member = fake_member('닉네임 | DisplayPlayer', member_id=42)
        assert await balancer_cog.resolve_player_name(member) == 'LinkedPlayer'

    async def test_falls_back_to_activity(self, balancer_cog: Balancer, monkeypatch):
        async def fake_request(endpoint: str, params: dict | None = None) -> dict:
            assert endpoint == 'players/abc123'
            return {'data': make_player_payload('ActivityPlayer')}

        monkeypatch.setattr(balancer_cog.balancer, '_request', fake_request)
        member = fake_member('닉네임 | DisplayPlayer', playing=True, party_id='abc123-def', member_id=7)

        assert await balancer_cog.resolve_player_name(member) == 'ActivityPlayer'
        # 조회에 성공하면 디스코드 계정이 연결된다.
        assert await balancer_cog.balancer.get_player_name_by_discord_id(7) == 'ActivityPlayer'

    async def test_falls_back_to_display_name(self, balancer_cog: Balancer):
        member = fake_member('닉네임 | DisplayPlayer', member_id=9)
        assert await balancer_cog.resolve_player_name(member) == 'DisplayPlayer'

    async def test_parse_command_input_without_argument(self, balancer_cog: Balancer):
        author = fake_member('닉네임 | AuthorPlayer', member_id=11)
        name, discord_id = await balancer_cog.parse_command_input(fake_context(author), None)

        assert (name, discord_id) == ('AuthorPlayer', 11)

    async def test_parse_command_input_with_plain_name(self, balancer_cog: Balancer):
        author = fake_member(member_id=11)
        name, discord_id = await balancer_cog.parse_command_input(fake_context(author), ' SonPANG ')

        assert (name, discord_id) == ('SonPANG', None)

    async def test_parse_command_input_with_mention(self, balancer_cog: Balancer):
        author = fake_member(member_id=11)
        target = fake_member('닉네임 | TargetPlayer', member_id=22)
        ctx = fake_context(author, {22: target})

        assert await balancer_cog.parse_command_input(ctx, '<@22>') == ('TargetPlayer', 22)

    async def test_unknown_mention_raises(self, balancer_cog: Balancer):
        ctx = fake_context(fake_member(member_id=11), {})
        with pytest.raises(PlayerNotFoundError):
            await balancer_cog.parse_command_input(ctx, '<@999>')


class TestGameLogic:
    @pytest.mark.parametrize(
        'user, bot, expected',
        [
            ('가위', '가위', 'draw'),
            ('가위', '보', 'win'),
            ('가위', '바위', 'lose'),
            ('보', '가위', 'lose'),
            ('보', '바위', 'win'),
            ('바위', '가위', 'win'),
        ],
    )
    def test_judge_rps(self, user: str, bot: str, expected: str):
        assert judge_rps(user, bot) == expected

    def test_all_combinations_are_decidable(self):
        outcomes = {judge_rps(user, bot) for user in RPS_CHOICES for bot in RPS_CHOICES}
        assert outcomes == {'win', 'lose', 'draw'}

    @pytest.mark.parametrize(
        'user_name, expected',
        [
            ('tester#1234', 'tester_1234.txt'),
            ('../../etc/passwd', 'etc_passwd.txt'),
            ('한글유저', '한글유저.txt'),
            ('', 'unknown.txt'),
        ],
    )
    def test_safe_file_name(self, user_name: str, expected: str):
        assert safe_file_name(user_name) == expected


@dataclass
class FakeVoice:
    connected: bool = True

    def is_connected(self) -> bool:
        return self.connected


def make_track(title: str) -> Track:
    return Track(info=TrackInfo(title=title, target_url=f'https://stream/{title}'), requester_id=1)


class TestGuildPlayerQueue:
    def _player(self, **kwargs) -> GuildPlayer:
        return GuildPlayer(guild_id=1, voice=FakeVoice(), text_channel=None, **kwargs)

    def test_pop_next_is_fifo(self):
        player = self._player(queue=[make_track('a'), make_track('b')])
        assert player.pop_next().title == 'a'
        assert player.pop_next().title == 'b'
        assert player.pop_next() is None

    def test_loop_keeps_current_track(self):
        current = make_track('a')
        player = self._player(queue=[make_track('b')], current=current, loop=True)
        assert player.pop_next() is current
        assert player.pop_next() is current
        assert len(player.queue) == 1  # 반복 중에는 대기열을 소비하지 않는다.

    def test_loop_without_current_falls_back_to_queue(self):
        player = self._player(queue=[make_track('b')], loop=True)
        assert player.pop_next().title == 'b'

    def test_shuffle_picks_from_queue(self):
        titles = {'a', 'b', 'c'}
        player = self._player(queue=[make_track(title) for title in sorted(titles)], shuffle=True)
        picked = {player.pop_next().title for _ in range(3)}
        assert picked == titles
