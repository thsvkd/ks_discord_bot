"""디스코드 봇 본체."""

from __future__ import annotations

import pkgutil

import discord
from discord.ext import commands

import ks_bot.cogs as cogs_package
from ks_bot.common.errors import KSBotError
from ks_bot.config import Settings
from ks_bot.help_command import CustomHelpCommand
from ks_bot.logging_config import get_logger

__all__ = ['KSBot', 'build_intents']

logger = get_logger(__name__)


def build_intents() -> discord.Intents:
    """봇이 필요로 하는 인텐트.

    `members`/`presences`는 디스코드 개발자 포털에서 별도로 켜야 하는 특권 인텐트다.
    """
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.presences = True
    return intents


class KSBot(commands.Bot):
    """설정을 주입받아 동작하는 봇.

    코그는 `setup_hook`에서 `ks_bot.cogs` 패키지를 스캔해 자동 로드한다.
    """

    def __init__(self, settings: Settings, **kwargs):
        super().__init__(
            command_prefix=settings.command_prefix,
            intents=kwargs.pop('intents', build_intents()),
            help_command=kwargs.pop('help_command', CustomHelpCommand()),
            **kwargs,
        )
        self.settings = settings

    async def setup_hook(self) -> None:
        await self.load_all_extensions()

    async def load_all_extensions(self) -> list[str]:
        """`ks_bot.cogs` 하위 모듈을 모두 로드하고, 성공한 확장 이름을 반환한다."""
        loaded: list[str] = []
        for module_info in pkgutil.iter_modules(cogs_package.__path__):
            if module_info.name.startswith('_'):
                continue

            extension = f'{cogs_package.__name__}.{module_info.name}'
            try:
                await self.load_extension(extension)
            except commands.ExtensionError:
                # 코그 하나가 실패해도 나머지는 계속 동작해야 한다.
                logger.exception('확장 로드에 실패했습니다: %s', extension)
                continue

            logger.info('확장을 로드했습니다: %s', extension)
            loaded.append(extension)
        return loaded

    async def on_ready(self) -> None:
        logger.info('로그인 완료: %s (ID: %s)', self.user, getattr(self.user, 'id', '?'))
        logger.info('접속한 서버 수: %d', len(self.guilds))

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """커맨드 예외를 사용자 친화적인 메시지로 변환한다."""
        if isinstance(error, commands.CommandNotFound):
            return

        original = getattr(error, 'original', error)

        if isinstance(original, KSBotError):
            await ctx.send(f'❌ {original.user_message}')
            logger.warning('커맨드 처리 중 도메인 오류. command=%s, error=%s', ctx.command, original)
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f'❌ 인자가 부족합니다. `{ctx.clean_prefix}도움말 {ctx.command}`을(를) 확인해주세요.')
            return

        if isinstance(error, commands.BadArgument):
            await ctx.send('❌ 입력값이 올바르지 않습니다.')
            return

        if isinstance(error, (commands.MissingPermissions, commands.BotMissingPermissions)):
            await ctx.send('❌ 이 명령을 실행할 권한이 없습니다.')
            return

        if isinstance(error, commands.NoPrivateMessage):
            await ctx.send('❌ 이 명령은 서버에서만 사용할 수 있습니다.')
            return

        if isinstance(error, commands.CheckFailure):
            await ctx.send('❌ 이 명령을 실행할 수 없습니다.')
            return

        logger.exception('처리되지 않은 커맨드 오류. command=%s', ctx.command, exc_info=original)
        await ctx.send('❌ 명령을 처리하는 중 오류가 발생했습니다.')

    async def on_member_join(self, member: discord.Member) -> None:
        guild = member.guild
        if guild.system_channel is not None:
            await guild.system_channel.send(f'{member.mention}님, {guild.name}에 오신 것을 환영합니다!')
