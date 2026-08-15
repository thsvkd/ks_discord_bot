"""PUBG 전투력(점수) 조회 코그."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta

import discord
from discord import Member
from discord.ext import commands, tasks

from ks_bot.bot import KSBot
from ks_bot.common.errors import KSBotError, PlayerNotFoundError
from ks_bot.core.pubg import PubgBalancer
from ks_bot.logging_config import get_logger

logger = get_logger(__name__)

PUBG_APP_NAME = 'PUBG: BATTLEGROUNDS'
EMBED_COLOR = 0xD04848
_MENTION_PATTERN = re.compile(r'^<@!?(?P<id>\d+)>$')

_LOADING_IMAGE = (
    'https://lh3.googleusercontent.com/u/0/drive-viewer/'
    'AEYmBYRiFGFgeh92WnsjsTBvEi1rxCKjEpbAYq3pi5FBM_asqA6nKFIOl885D9WzQJ6dC0Fj43nAGt0KQhOvtvlr1desweLuHQ=w2560-h1271'
)


@dataclass(frozen=True)
class ScoreTier:
    """점수 구간별 연출."""

    min_score: float
    title: str
    image_url: str


# 높은 점수부터 검사한다.
SCORE_TIERS: tuple[ScoreTier, ...] = (
    ScoreTier(
        15.0,
        '전투력 측정 완료! 스카우터가... 터져버렸어?!?',
        'https://lh3.googleusercontent.com/u/0/drive-viewer/'
        'AEYmBYQ3qw-Prf9G2V758nIn1Xzx3YLe5RTCI-ibi4Q7rtYHqC8283wYpqV0oS8PkNsyjwJGJWUOjOcf_ou1T9YnQ2PMyroC_w=w2560-h1271',
    ),
    ScoreTier(
        10.0,
        '전투력 측정 완료! 이, 이녀석 조심해야겠어...!',
        'https://lh3.googleusercontent.com/u/0/drive-viewer/'
        'AEYmBYRkUJv1XYMkyn4a-NPazFnnNQ09O7jTLBppgpjTxlpkJ1smPqIa2sJlBgurJP042ax5HfwTMnziXCdnHRbEt74WZS8low=w2560-h1271',
    ),
    ScoreTier(
        5.0,
        '전투력 측정 완료! 좀 치는 녀석이군...',
        'https://lh3.googleusercontent.com/u/0/drive-viewer/'
        'AEYmBYR1jHdQyQMvviH3lMQbCO8Q3qgOaFYBFGZ9qlOEOy7ikThM56R2L_PIyT2jkEpzYac0TZOPT9L09Fijb9VqIUOiYd0syw=w2560-h1271',
    ),
    ScoreTier(
        float('-inf'),
        '전투력 측정 완료! 애송이로군요!',
        'https://lh3.googleusercontent.com/u/0/drive-viewer/'
        'AEYmBYT7wt9V9d2PPR9BtqUb8beBULaeOCLojdCNPMdy5SZ0fOEzCuIS_v0f09CwtrnS8cDXeKGl7_m7EyGij9Fh1_i_VPOZRw=w2560-h1271',
    ),
)


def parse_discord_mention(text: str) -> int | None:
    """`<@123>` / `<@!123>` 형태의 멘션에서 디스코드 ID를 뽑는다."""
    match = _MENTION_PATTERN.match(text.strip()) if text else None
    return int(match.group('id')) if match else None


def parse_player_name_from_display_name(display_name: str) -> str:
    """`닉네임 | PUBG_ID` 형식의 표시 이름에서 PUBG 아이디를 추출한다.

    구분자가 없으면 표시 이름 전체를 그대로 사용한다.
    """
    if '|' in display_name:
        return display_name.rsplit('|', 1)[1].strip()
    return display_name.strip()


def parse_pubg_account_id(member: Member) -> str | None:
    """PUBG를 플레이 중인 멤버의 활동 정보에서 PUBG 계정 ID를 추출한다."""
    for activity in getattr(member, 'activities', ()) or ():
        if getattr(activity, 'name', None) != PUBG_APP_NAME:
            continue
        party = getattr(activity, 'party', None) or {}
        party_id = party.get('id') if isinstance(party, dict) else None
        if party_id:
            return party_id.split('-')[0]
    return None


def is_playing_pubg(member: Member) -> bool:
    return any(getattr(activity, 'name', None) == PUBG_APP_NAME for activity in getattr(member, 'activities', ()) or ())


def build_score_embed(player_name: str, score: float) -> discord.Embed:
    """점수 구간에 맞는 결과 임베드를 만든다."""
    tier = next(tier for tier in SCORE_TIERS if score >= tier.min_score)
    embed = discord.Embed(
        title=tier.title,
        description=f'**`{player_name}`**의 스탯 점수는 **`{score:.04f}`** 입니다.',
        color=EMBED_COLOR,
    )
    embed.set_image(url=tier.image_url)
    return embed


class Balancer(commands.Cog, name='밸런서'):
    """PUBG 전적 기반 전투력 측정."""

    def __init__(self, bot: KSBot):
        self.bot = bot
        settings = bot.settings
        self.balancer = PubgBalancer(
            api_key=settings.pubg_token,
            platform=settings.pubg_platform,
            db_path=settings.db_path,
            max_match_num=settings.max_match_num,
            player_cache_ttl=timedelta(hours=settings.player_cache_ttl_hours),
        )
        self.check_member_status.change_interval(minutes=settings.member_status_interval_minutes)

    async def cog_load(self) -> None:
        await self.balancer.connect()

    async def cog_unload(self) -> None:
        self.check_member_status.cancel()
        await self.balancer.aclose()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        # on_ready는 재접속 때마다 호출되므로 중복 시작을 막는다.
        if not self.check_member_status.is_running():
            self.check_member_status.start()

    # ---------- 백그라운드 작업 ----------

    @tasks.loop(minutes=30)
    async def check_member_status(self) -> None:
        """PUBG를 플레이 중인 멤버를 찾아 플레이어 정보를 갱신한다."""
        for guild in self.bot.guilds:
            for member in guild.members:
                account_id = parse_pubg_account_id(member)
                if not account_id:
                    continue
                try:
                    player = await self.balancer.sync_player_by_account_id(account_id, discord_id=member.id)
                    logger.debug('플레이어 정보를 갱신했습니다: %s (discord=%s)', player.name, member.id)
                except KSBotError as e:
                    # 한 명이 실패해도 루프 전체가 죽으면 안 된다.
                    logger.warning('플레이어 정보 갱신 실패. member=%s, error=%s', member, e)

    @check_member_status.before_loop
    async def before_check_member_status(self) -> None:
        await self.bot.wait_until_ready()

    @check_member_status.error
    async def on_check_member_status_error(self, error: BaseException) -> None:
        logger.exception('멤버 상태 확인 작업이 실패했습니다.', exc_info=error)

    # ---------- 입력 해석 ----------

    async def resolve_player_name(self, member: Member) -> str:
        """디스코드 멤버에 대응하는 PUBG 플레이어 이름을 찾는다.

        1) DB에 연결된 계정 → 2) 현재 PUBG 플레이 중이면 활동 정보 → 3) 표시 이름 파싱.
        """
        try:
            return await self.balancer.get_player_name_by_discord_id(member.id)
        except PlayerNotFoundError:
            pass

        account_id = parse_pubg_account_id(member)
        if account_id:
            try:
                player = await self.balancer.sync_player_by_account_id(account_id, discord_id=member.id)
                return player.name
            except KSBotError as e:
                logger.debug('활동 정보로 플레이어를 찾지 못했습니다. member=%s, error=%s', member, e)

        return parse_player_name_from_display_name(member.display_name)

    async def parse_command_input(self, ctx: commands.Context, raw_input: str | None) -> tuple[str, int | None]:
        """커맨드 인자를 (플레이어 이름, 디스코드 ID)로 해석한다."""
        if not raw_input:
            return await self.resolve_player_name(ctx.author), ctx.author.id

        discord_id = parse_discord_mention(raw_input)
        if discord_id is None:
            # 멘션이 아니면 PUBG 플레이어 이름으로 취급한다.
            return raw_input.strip(), None

        member = ctx.guild.get_member(discord_id) if ctx.guild else None
        if member is None:
            raise PlayerNotFoundError(player_name=raw_input)

        return await self.resolve_player_name(member), discord_id

    # ---------- 커맨드 ----------

    @commands.hybrid_command(
        name='점수',
        help='유저의 스탯 점수를 출력합니다.',
        description='유저의 스탯 점수를 출력합니다.',
        aliases=['실력', '스탯점수', '실력점수', 'score'],
    )
    @commands.guild_only()
    async def player_stats_score(self, ctx: commands.Context, *, input: str | None = None) -> None:
        loading_embed = discord.Embed(
            title='삐삑! 전투력 측정 중...',
            description='매치정보를 받아오는 중입니다, 잠시만 기다려주세요...',
            color=EMBED_COLOR,
        )
        loading_embed.set_image(url=_LOADING_IMAGE)
        message = await ctx.send(embed=loading_embed)

        try:
            player_name, discord_id = await self.parse_command_input(ctx, input)
            if discord_id is not None:
                await self.balancer.link_discord_account(player_name, discord_id)

            stats = await self.balancer.get_stats(player_name)
            await message.edit(embed=build_score_embed(player_name, stats.score))
        except KSBotError as e:
            logger.info('점수 조회 실패: %s', e)
            await message.edit(content=f'❌ {e.user_message}', embed=None)
        except Exception:
            logger.exception('점수 조회 중 예상치 못한 오류가 발생했습니다.')
            await message.edit(content='❌ 점수를 계산하는 중 오류가 발생했습니다.', embed=None)


async def setup(bot: KSBot) -> None:
    if not bot.settings.has_pubg_token:
        logger.warning('PUBG_TOKEN이 없어 밸런서 코그를 로드하지 않습니다.')
        return
    await bot.add_cog(Balancer(bot))
