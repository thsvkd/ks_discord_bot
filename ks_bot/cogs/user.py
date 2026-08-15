"""서버 멤버 관리(추방/차단/역할) 코그."""

from __future__ import annotations

import discord
from discord.ext import commands

from ks_bot.bot import KSBot
from ks_bot.logging_config import get_logger

logger = get_logger(__name__)


class User(commands.Cog, name='유저관리'):
    """관리 권한이 필요한 멤버 관리 커맨드."""

    def __init__(self, bot: KSBot):
        self.bot = bot

    @commands.hybrid_group(name='유저', help='서버 멤버 관리 커맨드입니다.', description='서버 멤버 관리 커맨드입니다.', invoke_without_command=True)
    @commands.guild_only()
    async def user_group(self, ctx: commands.Context) -> None:
        """`/유저`만 입력했을 때 하위 커맨드를 안내한다.

        슬래시로는 그룹 자체를 호출할 수 없으므로(디스코드 제약) 이 콜백은 접두사 전용이다.
        """
        await ctx.send_help(ctx.command)

    @user_group.command(name='추방', help='유저를 추방합니다.', description='유저를 추방합니다.')
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick_user(self, ctx: commands.Context, member: discord.Member) -> None:
        await member.kick(reason=f'요청자: {ctx.author}')
        await ctx.send(f'{member} 님이 추방되었습니다.')

    @user_group.command(name='차단', help='유저를 차단합니다.', description='유저를 차단합니다.')
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban_user(self, ctx: commands.Context, member: discord.Member) -> None:
        await member.ban(reason=f'요청자: {ctx.author}')
        await ctx.send(f'{member} 님이 차단되었습니다.')

    @user_group.command(name='차단해제', help='유저를 차단해제합니다.', description='유저를 차단해제합니다.')
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban_user(self, ctx: commands.Context, nickname: str) -> None:
        # discord.py 2.x의 `guild.bans()`는 비동기 이터레이터다.
        async for ban_entry in ctx.guild.bans():
            if nickname in (ban_entry.user.name, str(ban_entry.user)):
                await ctx.guild.unban(ban_entry.user, reason=f'요청자: {ctx.author}')
                await ctx.send(f'{nickname} 님이 차단 해제되었습니다.')
                return

        await ctx.send(f'{nickname} 님은 차단 목록에 없습니다.')

    @user_group.command(name='역할부여', help='유저에게 역할을 부여합니다.', description='유저에게 역할을 부여합니다.')
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_user(self, ctx: commands.Context, member: discord.Member, *, role_name: str) -> None:
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if role is None:
            await ctx.send(f'{role_name} 역할이 존재하지 않습니다.')
            return

        await member.add_roles(role, reason=f'요청자: {ctx.author}')
        await ctx.send(f'{member} 님에게 {role_name} 역할이 부여 되었습니다.')


async def setup(bot: KSBot) -> None:
    await bot.add_cog(User(bot))
