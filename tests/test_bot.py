"""봇 기동 배선 테스트.

디스코드 게이트웨이에 접속하지 않고, 코그가 실제로 모두 로드되는지 확인한다.
(예전에는 코그 로드 실패를 봇을 실행해봐야만 알 수 있었다.)
"""

from __future__ import annotations

import functools
import logging
from types import SimpleNamespace

import pytest

from ks_bot.bot import SENT_ID_MEMORY, KSBot, build_intents
from ks_bot.config import Settings

#: 커맨드는 카테고리 그룹 아래로 묶여 있으므로 전체 경로로 확인한다.
EXPECTED_COMMANDS = {'점수', '음악 재생', '게임 주사위', '게임 가위바위보', '메시지 숫자', '유저 추방', '음악 볼륨', '음악 대기리스트'}


class TestIntents:
    def test_required_intents_are_enabled(self):
        intents = build_intents()
        assert intents.message_content is True
        assert intents.members is True
        assert intents.presences is True


class TestExtensionLoading:
    async def test_all_cogs_load(self, bot: KSBot):
        loaded = await bot.load_all_extensions()

        assert {name.rsplit('.', 1)[1] for name in loaded} == {'balancer', 'game', 'giveaway', 'msg', 'music', 'user'}

    async def test_giveaway_cog_is_skipped_without_channel(self, bot: KSBot):
        """확장은 로드되지만, 채널 설정이 없으면 코그는 등록되지 않는다."""
        await bot.load_all_extensions()

        assert bot.get_cog('무료배포') is None

    async def test_commands_are_registered(self, bot: KSBot):
        await bot.load_all_extensions()

        names = {command.qualified_name for command in bot.walk_commands()}
        assert names >= EXPECTED_COMMANDS

    async def test_aliases_resolve(self, bot: KSBot):
        await bot.load_all_extensions()

        assert bot.get_command('score') is bot.get_command('점수')
        assert bot.get_command('음악 play') is bot.get_command('음악 재생')

    async def test_no_duplicate_command_names(self, bot: KSBot):
        """이름 충돌은 같은 부모 아래에서만 문제가 된다(`/음악 정지`와 `/게임 정지`는 공존 가능)."""
        await bot.load_all_extensions()

        seen: dict[str, set[str]] = {}
        for command in bot.walk_commands():
            scope = seen.setdefault(command.full_parent_name, set())
            for name in (command.name, *command.aliases):
                assert name not in scope, f'커맨드 이름이 중복됩니다: {command.full_parent_name} {name}'.strip()
                scope.add(name)

    async def test_balancer_is_skipped_without_pubg_token(self, settings: Settings):
        instance = KSBot(Settings(discord_token='t', pubg_token='', db_path=settings.db_path, game_result_dir=settings.game_result_dir))
        try:
            await instance.load_all_extensions()
            assert instance.get_cog('밸런서') is None
            assert instance.get_command('점수') is None
        finally:
            await instance.close()

    async def test_cog_unload_releases_resources(self, bot: KSBot):
        await bot.load_all_extensions()
        cog = bot.get_cog('밸런서')

        await bot.unload_extension('ks_bot.cogs.balancer')

        assert cog.balancer.repository.is_connected is False


class TestDuplicateInstanceDetection:
    """같은 토큰으로 봇을 두 벌 띄우면 모든 커맨드가 두 번 응답한다.

    실제로 겪었고, 원인이 코드인지 인스턴스인지 가리는 데 오래 걸렸다.
    """

    BOT_ID = 1122923125630304396

    def make_message(self, bot: KSBot, *, message_id: int, author_id: int, interaction: object = None, webhook_id: int | None = None):
        bot._connection.user = SimpleNamespace(id=self.BOT_ID, bot=True)
        return SimpleNamespace(
            id=message_id,
            author=SimpleNamespace(id=author_id, bot=True),
            channel=SimpleNamespace(id=999),
            interaction_metadata=interaction,
            webhook_id=webhook_id,
        )

    def test_my_own_message_is_not_flagged(self, bot: KSBot):
        bot._sent_message_ids.append(555)
        message = self.make_message(bot, message_id=555, author_id=self.BOT_ID)

        assert bot._is_from_another_instance(message) is False

    def test_message_from_another_instance_is_flagged(self, bot: KSBot):
        """내 계정이 보냈는데 내가 보낸 기록이 없다 = 다른 인스턴스."""
        message = self.make_message(bot, message_id=777, author_id=self.BOT_ID)

        assert bot._is_from_another_instance(message) is True

    def test_other_users_are_ignored(self, bot: KSBot):
        message = self.make_message(bot, message_id=777, author_id=1234)

        assert bot._is_from_another_instance(message) is False

    def test_slash_response_is_not_flagged(self, bot: KSBot):
        """슬래시 응답은 전송 시점에 ID를 돌려받지 못해 내 것과 구분되지 않는다."""
        message = self.make_message(bot, message_id=777, author_id=self.BOT_ID, interaction=object())

        assert bot._is_from_another_instance(message) is False

    def test_webhook_message_is_not_flagged(self, bot: KSBot):
        message = self.make_message(bot, message_id=777, author_id=self.BOT_ID, webhook_id=42)

        assert bot._is_from_another_instance(message) is False

    def test_warning_is_rate_limited(self, bot: KSBot, caplog: pytest.LogCaptureFixture):
        """메시지마다 찍으면 로그가 묻힌다."""
        message = self.make_message(bot, message_id=777, author_id=self.BOT_ID)

        with caplog.at_level(logging.WARNING):
            bot._warn_duplicate_instance(message)
            bot._warn_duplicate_instance(message)

        assert sum('다른 인스턴스' in record.message for record in caplog.records) == 1

    async def test_sent_ids_are_recorded_on_send(self, bot: KSBot):
        """`http.send_message`를 감싸 모든 전송 경로를 한 곳에서 기록한다."""

        async def fake_send(*args, **kwargs):
            return {'id': '12345'}

        # 래퍼는 `__init__`에서 이미 걸려 있다. 그 안쪽만 가짜로 바꾼다.
        bot._sent_message_ids.clear()
        original = bot.http.send_message
        bot.http.send_message = functools.wraps(fake_send)(fake_send)
        bot._track_sent_messages()
        try:
            await bot.http.send_message(1)
        finally:
            bot.http.send_message = original

        assert 12345 in bot._sent_message_ids

    def test_memory_is_bounded(self, bot: KSBot):
        """오래 돌아도 메모리가 무한히 늘지 않아야 한다."""
        for index in range(SENT_ID_MEMORY * 2):
            bot._sent_message_ids.append(index)

        assert len(bot._sent_message_ids) == SENT_ID_MEMORY
