"""봇 기동 배선 테스트.

디스코드 게이트웨이에 접속하지 않고, 코그가 실제로 모두 로드되는지 확인한다.
(예전에는 코그 로드 실패를 봇을 실행해봐야만 알 수 있었다.)
"""

from __future__ import annotations

from ks_bot.bot import KSBot, build_intents
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
