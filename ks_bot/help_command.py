"""커스텀 도움말 커맨드."""

from __future__ import annotations

from collections.abc import Iterable

import discord
from discord.ext import commands

__all__ = [
    'HELP_COMMAND_ATTRS',
    'CustomHelpCommand',
    'build_group_help_embed',
    'build_help_embed',
    'collect_command_mapping',
    'format_command_line',
    'iter_leaf_commands',
    'register_help_app_command',
]


def _chunk_lines(lines: list[str], limit: int = 1024) -> list[str]:
    """임베드 필드 값 길이 제한에 맞춰 줄을 묶는다."""
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for line in lines:
        addition = len(line) + 1
        if current and length + addition > limit:
            chunks.append('\n'.join(current))
            current, length = [], 0
        current.append(line)
        length += addition
    if current:
        chunks.append('\n'.join(current))
    return chunks


#: 도움말 커맨드로 인정할 이름들. `/help`와 `/도움말` 중 어느 쪽을 쳐도 동작해야 한다.
HELP_COMMAND_ATTRS = {
    'name': 'help',
    'aliases': ['도움말', '명령어', '커맨드', 'commands'],
    'help': '사용할 수 있는 커맨드 목록을 보여줍니다.',
    'description': '사용할 수 있는 커맨드 목록을 보여줍니다.',
}

#: 슬래시 도움말의 이름. 접두사 쪽 `help`와 이름을 나눠 두 경로가 서로 가리지 않게 한다.
SLASH_HELP_NAME = '도움말'


def iter_leaf_commands(command_list: Iterable[commands.Command]) -> list[commands.Command]:
    """실제로 실행할 수 있는 커맨드만 골라 이름순으로 반환한다.

    그룹은 그 자체로 호출할 수 없으므로(디스코드 제약) 목록에서 빼고 하위 커맨드를 펼친다.
    """
    leaves: list[commands.Command] = []
    for command in command_list:
        if command.hidden:
            continue
        if isinstance(command, commands.Group):
            leaves.extend(iter_leaf_commands(command.commands))
            continue
        leaves.append(command)
    return sorted(leaves, key=lambda command: command.qualified_name)


def format_command_line(command: commands.Command, prefix: str) -> str:
    """도움말 한 줄. 별칭이 있으면 함께 보여준다.

    별칭을 감추면 `/무료게임`은 알아도 `/무료`는 모르는 상황이 생긴다.
    그룹 하위 커맨드는 `/음악 재생`처럼 전체 경로로 보여야 그대로 따라 칠 수 있다.
    """
    line = f'`{prefix}{command.qualified_name}`'
    if command.aliases:
        line += f' ({", ".join(f"`{alias}`" for alias in command.aliases)})'
    return f'{line}\n　{command.help or command.description or "설명 없음"}'


def build_help_embed(mapping: dict[commands.Cog | None, list[commands.Command]], prefix: str) -> discord.Embed:
    """전체 커맨드 목록 임베드.

    접두사 도움말과 슬래시 도움말이 같은 내용을 보여주도록 여기에 모아둔다.
    """
    embed = discord.Embed(
        title='📖 도움말',
        description=f'사용할 수 있는 커맨드 목록입니다.\n`{prefix}help <커맨드>` 로 자세한 설명을 볼 수 있어요.',
        color=discord.Color.blue(),
    )

    # 코그 없는 커맨드(도움말 자신)는 마지막에 오도록 정렬한다.
    for cog, command_list in sorted(mapping.items(), key=lambda item: (item[0] is None, getattr(item[0], 'qualified_name', ''))):
        lines = [format_command_line(command, prefix) for command in iter_leaf_commands(command_list)]
        if not lines:
            continue

        # 임베드 필드 하나에 담기지 않으면 나눠 넣는다(음악 코그처럼 커맨드가 많은 경우).
        name = cog.qualified_name if cog else '기타'
        for index, chunk in enumerate(_chunk_lines(lines)):
            embed.add_field(name=name if index == 0 else f'{name} (계속)', value=chunk, inline=False)
    return embed


def build_group_help_embed(group: commands.Group, prefix: str) -> discord.Embed:
    """그룹 하나의 하위 커맨드 목록 임베드."""
    embed = discord.Embed(
        title=f'📖 {prefix}{group.qualified_name}',
        description=group.help or group.description or '',
        color=discord.Color.blue(),
    )
    lines = [format_command_line(command, prefix) for command in iter_leaf_commands(group.commands)]
    for index, chunk in enumerate(_chunk_lines(lines)):
        embed.add_field(name='커맨드' if index == 0 else '커맨드 (계속)', value=chunk, inline=False)
    return embed


def collect_command_mapping(bot: commands.Bot) -> dict[commands.Cog | None, list[commands.Command]]:
    """봇에 등록된 커맨드를 코그별로 묶는다."""
    mapping: dict[commands.Cog | None, list[commands.Command]] = {cog: list(cog.get_commands()) for cog in bot.cogs.values()}
    loose = [command for command in bot.commands if command.cog is None]
    if loose:
        mapping[None] = loose
    return mapping


class CustomHelpCommand(commands.HelpCommand):
    """코그별로 커맨드를 묶어 임베드로 보여준다."""

    def __init__(self, **options):
        options.setdefault('command_attrs', dict(HELP_COMMAND_ATTRS))
        super().__init__(**options)

    async def send_bot_help(self, mapping: dict[commands.Cog | None, list[commands.Command]]) -> None:
        await self.get_destination().send(embed=build_help_embed(mapping, self.context.clean_prefix))

    async def send_command_help(self, command: commands.Command) -> None:
        embed = discord.Embed(
            title=f'{self.context.clean_prefix}{command.qualified_name}',
            description=command.help or command.description or '설명 없음',
            color=discord.Color.blue(),
        )
        if command.aliases:
            embed.add_field(name='다른 이름', value=', '.join(f'`{alias}`' for alias in command.aliases), inline=False)
        if command.signature:
            embed.add_field(name='사용법', value=f'`{self.context.clean_prefix}{command.qualified_name} {command.signature}`', inline=False)
        await self.get_destination().send(embed=embed)

    async def send_group_help(self, group: commands.Group) -> None:
        """그룹 하위 커맨드 목록.

        기본 구현은 아무것도 보내지 않는다. 그러면 `/음악`만 쳤을 때 봇이 침묵하므로 직접 채운다.
        """
        await self.get_destination().send(embed=build_group_help_embed(group, self.context.clean_prefix))

    async def send_cog_help(self, cog: commands.Cog) -> None:
        prefix = self.context.clean_prefix
        embed = discord.Embed(title=f'📖 {cog.qualified_name}', description=cog.description or '', color=discord.Color.blue())
        lines = [format_command_line(command, prefix) for command in iter_leaf_commands(cog.get_commands())]
        if lines:
            for index, chunk in enumerate(_chunk_lines(lines)):
                embed.add_field(name='커맨드' if index == 0 else '커맨드 (계속)', value=chunk, inline=False)
        await self.get_destination().send(embed=embed)

    async def send_error_message(self, error: str) -> None:
        await self.get_destination().send(f'❌ {error}')


def register_help_app_command(bot: commands.Bot) -> None:
    """도움말의 슬래시 버전을 등록한다.

    discord.py의 `HelpCommand`는 접두사 전용이라 하이브리드로 만들 수 없다.
    도움말만 `/` 목록에서 빠지면 정작 커맨드를 찾는 방법을 못 찾게 되므로 따로 등록한다.
    """
    if bot.tree.get_command(SLASH_HELP_NAME) is not None:
        return

    @bot.tree.command(name=SLASH_HELP_NAME, description=HELP_COMMAND_ATTRS['description'])
    async def help_slash(interaction: discord.Interaction) -> None:
        prefix = bot.command_prefix if isinstance(bot.command_prefix, str) else '/'
        embed = build_help_embed(collect_command_mapping(bot), prefix)
        await interaction.response.send_message(embed=embed, ephemeral=True)
