"""디스코드 봇 본체."""

from __future__ import annotations

import functools
import pkgutil
from collections import deque
from datetime import datetime, timedelta

import discord
from discord.ext import commands

import ks_bot.cogs as cogs_package
from ks_bot.common.errors import KSBotError
from ks_bot.common.timeutil import datetime_now
from ks_bot.config import Settings
from ks_bot.help_command import CustomHelpCommand, register_help_app_command
from ks_bot.logging_config import get_logger

__all__ = ['KSBot', 'build_intents']

logger = get_logger(__name__)

#: 중복 인스턴스 판별을 위해 기억해 둘 최근 전송 메시지 수.
#: 커맨드 하나가 여러 메시지를 보내기도 하므로 넉넉하게 잡는다.
SENT_ID_MEMORY = 256

#: 같은 경고를 매 메시지마다 찍으면 로그가 묻힌다.
DUPLICATE_WARNING_INTERVAL = timedelta(minutes=10)


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
        self._sent_message_ids: deque[int] = deque(maxlen=SENT_ID_MEMORY)
        self._last_duplicate_warning: datetime | None = None
        self._track_sent_messages()

    # ---------- 중복 인스턴스 감지 ----------

    def _track_sent_messages(self) -> None:
        """이 프로세스가 보낸 메시지의 ID를 기억해 둔다.

        같은 토큰으로 봇을 두 벌 띄우면 두 인스턴스가 모두 커맨드에 응답해서
        모든 메시지가 두 번 나간다. 실제로 그런 적이 있었고, 원인이 코드에 있는지
        인스턴스에 있는지 가리는 데 반나절이 걸렸다. 내가 보낸 것을 알고 있으면
        "내 계정인데 내가 보내지 않은 메시지"를 보고 즉시 알아챌 수 있다.
        """
        original = self.http.send_message

        @functools.wraps(original)
        async def tracked(*args, **kwargs):
            data = await original(*args, **kwargs)
            try:
                self._sent_message_ids.append(int(data['id']))
            except (KeyError, TypeError, ValueError):
                # ID를 못 읽어도 전송 자체는 성공했다. 감지만 포기한다.
                logger.debug('전송한 메시지의 ID를 읽지 못했습니다.')
            return data

        self.http.send_message = tracked

    def _is_from_another_instance(self, message: discord.Message) -> bool:
        """내 계정이 보냈지만 이 프로세스가 보내지 않은 메시지인지."""
        if self.user is None or message.author.id != self.user.id:
            return False
        if message.id in self._sent_message_ids:
            return False
        # 슬래시 응답과 웹훅 전송은 전송 시점에 ID를 돌려받지 못해 내 것과 구분되지 않는다.
        return message.interaction_metadata is None and message.webhook_id is None

    def _warn_duplicate_instance(self, message: discord.Message) -> None:
        """중복 인스턴스 경고. 메시지마다 찍으면 로그가 묻히므로 간격을 둔다."""
        now = datetime_now()
        if self._last_duplicate_warning is not None and now - self._last_duplicate_warning < DUPLICATE_WARNING_INTERVAL:
            return

        self._last_duplicate_warning = now
        logger.warning(
            '같은 봇 계정으로 도는 다른 인스턴스가 있는 것 같습니다. '
            '내가 보내지 않은 내 메시지를 발견했습니다. message_id=%s, channel_id=%s. '
            '같은 DISCORD_TOKEN을 쓰는 프로세스를 하나만 남겨주세요.',
            message.id,
            getattr(message.channel, 'id', '?'),
        )

    async def on_message(self, message: discord.Message) -> None:
        if self._is_from_another_instance(message):
            self._warn_duplicate_instance(message)
        # 봇이 보낸 메시지는 `process_commands`가 알아서 무시한다.
        await self.process_commands(message)

    async def setup_hook(self) -> None:
        await self.load_all_extensions()
        register_help_app_command(self)
        await self.sync_commands()

    async def sync_commands(self) -> list:
        """슬래시 커맨드를 디스코드에 등록한다.

        하이브리드 커맨드는 등록해야 비로소 `/` 목록과 `+` → "앱 사용" 메뉴에 나타난다.
        전역 등록은 반영까지 최대 1시간이 걸리므로, 길드 ID가 설정돼 있으면 그쪽으로도
        복사해 즉시 쓸 수 있게 한다.
        """
        guild_id = self.settings.slash_guild_id
        try:
            if guild_id:
                guild = discord.Object(id=guild_id)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logger.info('슬래시 커맨드 %d개를 길드(%s)에 등록했습니다.', len(synced), guild_id)
            else:
                synced = await self.tree.sync()
                logger.info('슬래시 커맨드 %d개를 전역 등록했습니다. (반영까지 최대 1시간)', len(synced))
            return synced
        except discord.HTTPException:
            # 등록에 실패해도 접두사 커맨드는 그대로 동작해야 한다.
            logger.exception('슬래시 커맨드 등록에 실패했습니다. 접두사 커맨드는 계속 사용할 수 있습니다.')
            return []

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
