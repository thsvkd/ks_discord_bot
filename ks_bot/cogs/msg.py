"""메시지/리액션 관련 예제 코그."""

from __future__ import annotations

import asyncio

import discord
from discord.ext import commands

from ks_bot.bot import KSBot
from ks_bot.logging_config import get_logger

logger = get_logger(__name__)

BANNED_EMOJI = '👎'
SAMPLE_IMAGE_URL = 'https://cdn.discordapp.com/attachments/721307978455580742/762760779409129513/img.png'


class Msg(commands.Cog, name='메시지'):
    """메시지 전송/수정/삭제와 리액션 처리."""

    def __init__(self, bot: KSBot):
        self.bot = bot

    @commands.Cog.listener('on_raw_reaction_add')
    async def remove_thumbsdown(self, payload: discord.RawReactionActionEvent) -> None:
        """따봉 반대 이모지는 즉시 제거한다."""
        # 채널/메시지 조회는 비싸므로 조건을 먼저 확인한다.
        if payload.emoji.name != BANNED_EMOJI or payload.user_id == self.bot.user.id:
            return

        try:
            channel = self.bot.get_channel(payload.channel_id) or await self.bot.fetch_channel(payload.channel_id)
            message = await channel.fetch_message(payload.message_id)
            await message.clear_reaction(BANNED_EMOJI)
        except discord.HTTPException:
            logger.warning('리액션을 제거하지 못했습니다. message_id=%s', payload.message_id)

    @commands.hybrid_group(
        name='메시지',
        help='메시지 전송/수정/삭제 관련 커맨드입니다.',
        description='메시지 전송/수정/삭제 관련 커맨드입니다.',
        invoke_without_command=True,
    )
    async def msg_group(self, ctx: commands.Context) -> None:
        """`/메시지`만 입력했을 때 하위 커맨드를 안내한다.

        슬래시로는 그룹 자체를 호출할 수 없으므로(디스코드 제약) 이 콜백은 접두사 전용이다.
        """
        await ctx.send_help(ctx.command)

    @msg_group.command(name='숫자', help='입력한 숫자를 보여줍니다', description='입력한 숫자를 보여줍니다', aliases=['number'])
    async def num_echo(self, ctx: commands.Context, user: int) -> None:
        await ctx.send(f'입력한 숫자는 {user}입니다.')

    @num_echo.error
    async def num_echo_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, (commands.BadArgument, commands.MissingRequiredArgument)):
            await ctx.send('정수를 입력 해주세요')

    @msg_group.command(name='임베드', help='임베드를 보여줍니다', description='임베드를 보여줍니다', aliases=['embed'])
    async def embed(self, ctx: commands.Context) -> None:
        embed = discord.Embed(title='Embed title', description='Embed description', color=0x36CCF2)
        embed.set_thumbnail(url=SAMPLE_IMAGE_URL)
        embed.set_image(url=SAMPLE_IMAGE_URL)
        for index in range(1, 5):
            embed.add_field(name=f'field_name{index}', value=f'field value{index}', inline=False)
        embed.set_footer(text='footer_text', icon_url=SAMPLE_IMAGE_URL)
        embed.set_author(name='author_name', url='https://velog.io/@chaejm55', icon_url=SAMPLE_IMAGE_URL)

        await ctx.send(embed=embed)

    @msg_group.command(name='삭제', help='메시지를 삭제합니다', description='메시지를 삭제합니다', aliases=['delete'])
    async def delete_msg(self, ctx: commands.Context) -> None:
        msg = await ctx.send('3초 뒤에 삭제 됩니다!')
        await msg.delete(delay=3)

    @msg_group.command(name='수정', help='메시지를 수정합니다', description='메시지를 수정합니다', aliases=['edit'])
    async def edit_msg(self, ctx: commands.Context) -> None:
        msg = await ctx.send('곧 수정 됩니다!')
        await msg.edit(content='수정 되었습니다!')

    @msg_group.command(name='따봉', help='메시지에 반응을 추가합니다', description='메시지에 반응을 추가합니다', aliases=['reaction'])
    async def reaction(self, ctx: commands.Context) -> None:
        # 슬래시로 부르면 원본 메시지가 없다(`ctx.message`가 None).
        # 그때는 새 메시지를 보내고 거기에 반응을 단다.
        target = ctx.message or await ctx.send('👍')
        await target.add_reaction('👍')

    @msg_group.command(name='기다리기', help='유저의 메시지를 기다립니다', description='유저의 메시지를 기다립니다', aliases=['wait'])
    async def wait(self, ctx: commands.Context) -> None:
        timeout = 5
        await ctx.send(f'{timeout}초간 기다립니다!')

        def check(m: discord.Message) -> bool:
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=timeout)
        except asyncio.TimeoutError:
            await ctx.send(f'시간초과 입니다...({timeout}초)')
        else:
            await ctx.send(f'{msg.content} 메시지를 {timeout}초 안에 입력하셨습니다!')


async def setup(bot: KSBot) -> None:
    await bot.add_cog(Msg(bot))
