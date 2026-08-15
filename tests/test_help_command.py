"""도움말 커맨드 테스트."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from discord.ext import commands

from ks_bot.bot import KSBot
from ks_bot.help_command import HELP_COMMAND_ATTRS, _chunk_lines, format_command_line


def make_command(name: str, *, aliases: list[str] | None = None, help_text: str = '') -> commands.Command:
    async def callback(ctx):  # pragma: no cover - 호출하지 않는다
        pass

    return commands.Command(callback, name=name, aliases=aliases or [], help=help_text)


class TestHelpRegistration:
    async def test_korean_alias_resolves_to_the_same_command(self, bot: KSBot):
        """`bot.py`의 오류 메시지가 `/도움말`을 안내하므로 실제로 존재해야 한다."""
        await bot.load_all_extensions()

        assert bot.get_command('도움말') is bot.get_command('help')

    @pytest.mark.parametrize('name', ['help', '도움말', '명령어', '커맨드', 'commands'])
    async def test_every_documented_name_works(self, bot: KSBot, name: str):
        await bot.load_all_extensions()
        assert bot.get_command(name) is not None

    async def test_help_command_has_description(self, bot: KSBot):
        """설명이 없으면 도움말 목록에 '설명 없음'으로 뜬다."""
        await bot.load_all_extensions()
        assert bot.get_command('help').help

    def test_alias_list_has_no_duplicates(self):
        aliases = HELP_COMMAND_ATTRS['aliases']
        assert len(aliases) == len(set(aliases))
        assert HELP_COMMAND_ATTRS['name'] not in aliases


class TestFormatCommandLine:
    def test_shows_prefix_and_description(self):
        line = format_command_line(make_command('점수', help_text='스탯 점수를 출력합니다.'), '/')

        assert line.startswith('`/점수`')
        assert '스탯 점수를 출력합니다.' in line

    def test_shows_aliases(self):
        """별칭을 감추면 `/무료게임`은 알아도 `/무료`는 모르게 된다."""
        line = format_command_line(make_command('무료게임', aliases=['무료', 'freegames']), '/')

        assert '`무료`' in line
        assert '`freegames`' in line

    def test_command_without_description(self):
        assert '설명 없음' in format_command_line(make_command('주사위'), '/')

    def test_respects_custom_prefix(self):
        assert format_command_line(make_command('점수'), '!').startswith('`!점수`')


class TestChunkLines:
    def test_short_input_stays_in_one_chunk(self):
        assert _chunk_lines(['a', 'b', 'c']) == ['a\nb\nc']

    def test_splits_when_over_the_limit(self):
        """디스코드 임베드 필드는 1024자까지다. 넘으면 전송 자체가 실패한다."""
        chunks = _chunk_lines(['x' * 400] * 5)

        assert len(chunks) > 1
        assert all(len(chunk) <= 1024 for chunk in chunks)

    def test_no_line_is_lost(self):
        lines = [f'line-{index}' * 30 for index in range(40)]
        assert sum(chunk.count('line-') for chunk in _chunk_lines(lines)) == sum(line.count('line-') for line in lines)

    def test_empty_input(self):
        assert _chunk_lines([]) == []

    def test_single_oversized_line_is_kept(self):
        """한 줄이 제한을 넘어도 통째로 버리지는 않는다."""
        assert len(_chunk_lines(['y' * 2000])) == 1


class TestCommandCoverage:
    async def test_every_command_has_help_text(self, bot: KSBot):
        """도움말에 '설명 없음'으로 뜨는 커맨드가 없어야 한다."""
        await bot.load_all_extensions()

        missing = [command.qualified_name for command in bot.commands if not command.hidden and not (command.help or command.description)]

        assert missing == []

    async def test_no_alias_collides_with_a_command_name(self, bot: KSBot):
        await bot.load_all_extensions()

        names = {command.name for command in bot.commands}
        collisions = [(command.name, alias) for command in bot.commands for alias in command.aliases if alias in names]

        assert collisions == []


def test_help_attrs_are_plain_data():
    """`command_attrs`는 discord.py가 그대로 소비하므로 단순 값이어야 한다."""
    assert isinstance(HELP_COMMAND_ATTRS, dict)
    assert all(isinstance(value, (str, list)) for value in HELP_COMMAND_ATTRS.values())
    assert SimpleNamespace(**HELP_COMMAND_ATTRS).name == 'help'
