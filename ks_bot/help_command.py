"""커스텀 도움말 커맨드."""

from __future__ import annotations

import discord
from discord.ext import commands

__all__ = ['CustomHelpCommand']


class CustomHelpCommand(commands.HelpCommand):
    """코그별로 커맨드를 묶어 임베드로 보여준다."""

    async def send_bot_help(self, mapping: dict[commands.Cog | None, list[commands.Command]]) -> None:
        embed = discord.Embed(title='도움말', description='사용할 수 있는 커맨드 목록입니다.', color=discord.Color.blue())

        for cog, command_list in mapping.items():
            lines = [f'`{command.name}`: {command.help or "설명 없음"}' for command in command_list if not command.hidden]
            if lines:
                embed.add_field(name=cog.qualified_name if cog else '기타', value='\n'.join(lines), inline=False)

        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command: commands.Command) -> None:
        embed = discord.Embed(
            title=f'{self.context.clean_prefix}{command.qualified_name}',
            description=command.help or command.description or '설명 없음',
            color=discord.Color.blue(),
        )
        if command.aliases:
            embed.add_field(name='다른 이름', value=', '.join(f'`{alias}`' for alias in command.aliases), inline=False)
        await self.get_destination().send(embed=embed)

    async def send_error_message(self, error: str) -> None:
        await self.get_destination().send(f'❌ {error}')
