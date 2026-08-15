"""무료 배포 알림 코그.

주기적으로 무료 배포를 수집해, 아직 알리지 않은 것만 채널에 발행한다.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime

import discord
from discord.ext import commands, tasks

from ks_bot.bot import KSBot
from ks_bot.common.giveaway import ClaimKind, Giveaway
from ks_bot.common.timeutil import datetime_now
from ks_bot.core.giveaway import SOURCE_EPIC, SOURCE_GAMERPOWER, GiveawayService
from ks_bot.logging_config import get_logger

logger = get_logger(__name__)

# 한 주기에 발행할 최대 건수. 수집처가 대량으로 밀어 넣어도 채널이 도배되지 않게 한다.
MAX_ANNOUNCE_PER_RUN = 8

# 디스코드가 한 메시지에 허용하는 임베드 수.
MAX_EMBEDS_PER_MESSAGE = 10

# 디스코드 임베드 길이 제한.
_TITLE_LIMIT = 256
_DESCRIPTION_LIMIT = 4096
_FIELD_VALUE_LIMIT = 1024
_BUTTON_LABEL_LIMIT = 80

_LIST_EMBED_COLOR = 0x57F287

# 수집처 식별자를 사람이 읽는 이름으로.
_SOURCE_LABELS = {SOURCE_EPIC: 'Epic Games', SOURCE_GAMERPOWER: 'GamerPower'}


def _truncate(text: str, limit: int) -> str:
    text = (text or '').strip()
    return text if len(text) <= limit else f'{text[: limit - 1]}…'


def format_timestamp(value: datetime, style: str = 'f') -> str:
    """디스코드 타임스탬프 마크업.

    보는 사람의 시간대로 자동 렌더되고, `R` 스타일은 남은 시간이 계속 갱신된다.
    UTC 문자열을 그대로 박아두는 것보다 훨씬 읽기 쉽다.
    """
    return f'<t:{int(value.timestamp())}:{style}>'


def _author_line(giveaway: Giveaway, *, compact: bool) -> str:
    """임베드 상단 줄.

    묶어서 보낼 때는 머리말이 이미 상태를 말해주므로 스토어만 남긴다.
    다만 마감 임박은 카드마다 다를 수 있어 그대로 표시한다.
    """
    if giveaway.is_ending_soon:
        return f'🔥 마감 임박 · {giveaway.store.label}'
    if compact:
        return giveaway.store.label
    if giveaway.is_upcoming:
        return f'🗓️ 배포 예정 · {giveaway.store.label}'
    return f'🎁 무료 배포 · {giveaway.store.label}'


def _price_text(giveaway: Giveaway) -> str:
    if giveaway.original_price:
        return f'~~{giveaway.original_price}~~ → **무료**'
    return '**무료**'


def _schedule_field(giveaway: Giveaway) -> tuple[str, str]:
    """(필드 이름, 값). 예정 배포는 시작 시각을, 진행 중인 배포는 마감을 보여준다."""
    if giveaway.is_upcoming and giveaway.starts_at:
        return '🗓️ 시작', f'{format_timestamp(giveaway.starts_at)}\n{format_timestamp(giveaway.starts_at, "R")}'
    if giveaway.ends_at:
        return '⏰ 마감', f'{format_timestamp(giveaway.ends_at)}\n{format_timestamp(giveaway.ends_at, "R")}'
    return '⏰ 마감', '미정'


def build_giveaway_embed(giveaway: Giveaway, *, compact: bool = False) -> discord.Embed:
    """배포 1건을 카드 형태로 렌더한다.

    Args:
        compact: 한 메시지에 여러 건을 묶을 때 사용한다. 큰 이미지를 쓰면 메시지가
            지나치게 길어지므로 우측 썸네일로 대체한다.
    """
    description_lines = []
    if giveaway.genres:
        description_lines.append(f'*{" · ".join(giveaway.genres)}*')
    if giveaway.description:
        description_lines.append(giveaway.description)

    embed = discord.Embed(
        title=_truncate(giveaway.title, _TITLE_LIMIT),
        url=giveaway.url or None,
        description=_truncate('\n'.join(description_lines), _DESCRIPTION_LIMIT) or None,
        color=giveaway.store.color,
    )
    embed.set_author(name=_truncate(_author_line(giveaway, compact=compact), _TITLE_LIMIT))
    embed.add_field(name='💰 가격', value=_truncate(_price_text(giveaway), _FIELD_VALUE_LIMIT), inline=True)

    schedule_name, schedule_value = _schedule_field(giveaway)
    embed.add_field(name=schedule_name, value=_truncate(schedule_value, _FIELD_VALUE_LIMIT), inline=True)

    if giveaway.claim_kind is ClaimKind.KEY_DROP:
        embed.add_field(
            name='🔑 받는 방법',
            value='선착순 키 배포입니다. 수량이 소진되면 마감 전에도 끝날 수 있어요.',
            inline=False,
        )

    if giveaway.thumbnail_url:
        if compact:
            embed.set_thumbnail(url=giveaway.thumbnail_url)
        else:
            embed.set_image(url=giveaway.thumbnail_url)

    footer_parts = [
        part
        for part in (
            f'메타크리틱 {giveaway.metacritic}' if giveaway.metacritic else '',
            f'출처 {_SOURCE_LABELS.get(giveaway.source, giveaway.source)}' if giveaway.source else '',
        )
        if part
    ]
    if footer_parts:
        embed.set_footer(text=' · '.join(footer_parts))
    return embed


def button_label(giveaway: Giveaway, *, standalone: bool = True) -> str:
    """버튼 문구.

    여러 건을 한 메시지에 묶으면 버튼도 나란히 놓이므로, 어느 게임의 버튼인지가
    가장 중요한 정보가 된다. 그래서 이때는 게임 이름을 쓴다.

    한 건만 있을 때는 어디로 가는지가 더 유용한데, 키 배포는 스토어가 아니라
    배포 사이트로 이동하는 경우가 많아 `Steam에서 받기`라고 쓰면 실제와 어긋난다.
    """
    if not standalone:
        return giveaway.title
    if giveaway.claim_kind is ClaimKind.KEY_DROP:
        return '받으러 가기'
    return f'{giveaway.store.label}에서 받기'


class GiveawayLinkView(discord.ui.View):
    """각 배포의 스토어로 바로 가는 링크 버튼 모음.

    링크 버튼은 상호작용 처리가 필요 없어 봇이 재시작돼도 계속 동작한다.
    """

    def __init__(self, giveaways: Sequence[Giveaway]):
        super().__init__(timeout=None)
        standalone = len(giveaways) == 1
        for giveaway in giveaways:
            self.add_item(
                discord.ui.Button(
                    label=_truncate(button_label(giveaway, standalone=standalone), _BUTTON_LABEL_LIMIT),
                    url=giveaway.url,
                    style=discord.ButtonStyle.link,
                    emoji='🎁',
                )
            )


def build_list_embed(giveaways: list[Giveaway]) -> discord.Embed:
    """`/무료게임` 커맨드용 요약 목록."""
    embed = discord.Embed(
        title='🎁 지금 받을 수 있는 무료 게임',
        description=f'총 **{len(giveaways)}건**입니다.',
        color=_LIST_EMBED_COLOR,
    )
    for giveaway in giveaways[:25]:
        deadline = f'{format_timestamp(giveaway.ends_at, "R")} 마감' if giveaway.ends_at else '마감 미정'
        key_note = ' · 선착순 키' if giveaway.claim_kind is ClaimKind.KEY_DROP else ''
        embed.add_field(
            name=_truncate(f'{giveaway.title} ({giveaway.store.label})', _TITLE_LIMIT),
            value=_truncate(f'[받으러 가기]({giveaway.url}) · {deadline}{key_note}', _FIELD_VALUE_LIMIT),
            inline=False,
        )
    return embed


def group_for_announcement(giveaways: Iterable[Giveaway]) -> list[tuple[str, list[Giveaway]]]:
    """발행 단위로 묶는다. 반환값은 (머리말, 항목들) 목록이고, 각 항목이 메시지 하나가 된다.

    건마다 메시지를 따로 보내면 채널이 시끄러워진다. 그래서 한 메시지에 여러 카드를 담되,
    **지금 받을 수 있는 것**과 **아직 시작하지 않은 것**은 나눈다. 사용자가 지금 해야 할
    행동이 다르기 때문에, 이 둘을 섞으면 오히려 읽기 어려워진다.

    한 그룹 안에서는 같은 스토어끼리 모아 임베드 색이 이어지게 하고, 그다음 마감이 빠른 순으로 둔다.
    """
    far_future = datetime.max.replace(tzinfo=datetime_now().tzinfo)
    items = list(giveaways)

    groups: list[tuple[str, list[Giveaway]]] = []
    for label, is_in_group in (
        ('🎁 지금 무료로 받을 수 있어요', lambda g: not g.is_upcoming),
        ('🗓️ 곧 무료로 풀립니다', lambda g: g.is_upcoming),
    ):
        members = sorted(
            (item for item in items if is_in_group(item)),
            key=lambda g: (g.store.value, g.ends_at or far_future, g.title),
        )
        # 디스코드 한 메시지의 임베드 수 제한을 넘으면 나눠 보낸다.
        for start in range(0, len(members), MAX_EMBEDS_PER_MESSAGE):
            groups.append((label, members[start : start + MAX_EMBEDS_PER_MESSAGE]))
    return groups


def build_group_header(label: str, giveaways: Sequence[Giveaway], mention: str = '') -> str:
    """묶음 머리말. 스토어 구성을 함께 보여줘 한눈에 파악되게 한다."""
    stores = sorted({giveaway.store.label for giveaway in giveaways})
    summary = f'{label} · **{len(giveaways)}건**'
    if stores:
        summary = f'{summary} ({", ".join(stores)})'
    return ' '.join(filter(None, (mention, summary)))


class GiveawayCog(commands.Cog, name='무료배포'):
    """무료로 풀린 게임을 찾아 알려준다."""

    def __init__(self, bot: KSBot):
        self.bot = bot
        settings = bot.settings
        self.channel_id = settings.giveaway_channel_id
        self.mention_role_id = settings.giveaway_mention_role_id
        self.service = GiveawayService(
            settings.db_path,
            stores=settings.giveaway_stores,
            include_upcoming=settings.giveaway_include_upcoming,
        )
        self.check_giveaways.change_interval(minutes=settings.giveaway_interval_minutes)

    async def cog_load(self) -> None:
        await self.service.connect()

    async def cog_unload(self) -> None:
        self.check_giveaways.cancel()
        await self.service.aclose()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        # on_ready는 재접속 때마다 호출되므로 중복 시작을 막는다.
        if not self.check_giveaways.is_running():
            self.check_giveaways.start()

    # ---------- 백그라운드 작업 ----------

    @tasks.loop(minutes=30)
    async def check_giveaways(self) -> None:
        channel = self.bot.get_channel(self.channel_id)
        if channel is None:
            logger.warning('무료 배포 채널을 찾을 수 없습니다: %s', self.channel_id)
            return

        # 최초 실행 판정은 발행 이력을 남기기 전에 해야 한다.
        is_first_run = await self.service.repository.is_empty()
        fresh = await self.service.find_new()
        await self.service.repository.purge_expired()

        if not fresh:
            logger.debug('새로 알릴 무료 배포가 없습니다.')
            return

        if is_first_run:
            # 봇을 처음 켠 시점에 이미 진행 중이던 배포를 한꺼번에 쏟아내지 않는다.
            await self.service.repository.mark_all_announced(fresh)
            logger.info('최초 실행이라 기존 배포 %d건을 발행 없이 기록했습니다.', len(fresh))
            return

        await self.announce(channel, fresh)

    @check_giveaways.before_loop
    async def before_check_giveaways(self) -> None:
        await self.bot.wait_until_ready()

    @check_giveaways.error
    async def on_check_giveaways_error(self, error: BaseException) -> None:
        logger.exception('무료 배포 확인 작업이 실패했습니다.', exc_info=error)

    # ---------- 발행 ----------

    @property
    def mention_text(self) -> str:
        return f'<@&{self.mention_role_id}>' if self.mention_role_id else ''

    async def announce(self, channel: discord.abc.Messageable, giveaways: list[Giveaway]) -> int:
        """배포 목록을 묶어서 발행하고, 발행에 성공한 건수를 반환한다.

        건마다 메시지를 나누면 채널이 시끄러워지므로 상태별로 묶어 메시지 수를 줄인다.
        """
        batch = giveaways[:MAX_ANNOUNCE_PER_RUN]
        if len(giveaways) > len(batch):
            logger.warning(
                '무료 배포 %d건 중 %d건만 이번에 발행합니다. 나머지는 다음 주기에 발행됩니다.',
                len(giveaways),
                len(batch),
            )

        announced = 0
        mention_used = False
        for label, group in group_for_announcement(batch):
            if not group:
                continue

            # 역할 멘션은 첫 메시지에만 넣는다. 묶음마다 반복하면 알림이 시끄러워진다.
            mention = '' if mention_used else self.mention_text
            compact = len(group) > 1

            try:
                message = await channel.send(
                    content=build_group_header(label, group, mention),
                    embeds=[build_giveaway_embed(giveaway, compact=compact) for giveaway in group],
                    view=GiveawayLinkView(group),
                )
            except discord.HTTPException:
                # 한 묶음이 실패해도 나머지는 계속 발행한다.
                # 기록을 남기지 않으므로 다음 주기에 재시도된다.
                logger.exception('무료 배포 발행에 실패했습니다: %s', [giveaway.key for giveaway in group])
                continue

            mention_used = True
            await self.service.repository.mark_all_announced(group, message.id)
            announced += len(group)

        logger.info('무료 배포 %d건을 발행했습니다.', announced)
        return announced

    # ---------- 커맨드 ----------

    @commands.hybrid_command(
        name='무료게임',
        help='지금 무료로 받을 수 있는 게임을 보여줍니다.',
        description='지금 무료로 받을 수 있는 게임을 보여줍니다.',
        aliases=['무료배포', '무료', 'freegames'],
    )
    async def list_giveaways(self, ctx: commands.Context) -> None:
        active = await self.service.repository.list_active()
        if not active:
            await ctx.send('지금 진행 중인 무료 배포가 없습니다. 새로 올라오면 알려드릴게요!')
            return
        await ctx.send(embed=build_list_embed(active))


async def setup(bot: KSBot) -> None:
    if not bot.settings.has_giveaway_channel:
        logger.warning('KS_BOT_GIVEAWAY_CHANNEL_ID가 없어 무료 배포 코그를 로드하지 않습니다.')
        return
    await bot.add_cog(GiveawayCog(bot))
