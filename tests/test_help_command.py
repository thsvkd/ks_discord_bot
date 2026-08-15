"""도움말 커맨드 테스트."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from discord import app_commands
from discord.ext import commands

from ks_bot.bot import KSBot
from ks_bot.help_command import (
    HELP_COMMAND_ATTRS,
    SLASH_HELP_NAME,
    _chunk_lines,
    build_group_help_embed,
    build_help_embed,
    collect_command_mapping,
    format_command_line,
    register_help_app_command,
)

#: 그룹 이름 → 그 아래에 반드시 있어야 하는 하위 커맨드.
EXPECTED_GROUPS = {
    '음악': {'재생', '정지', '스킵', '일시정지', '계속재생', '볼륨', '반복', '랜덤재생', '대기리스트', '강제연결해제'},
    '메시지': {'숫자', '임베드', '삭제', '수정', '따봉', '기다리기'},
    '유저': {'추방', '차단', '차단해제', '역할부여'},
    '게임': {'주사위', '뽑기', '가위바위보', '전적'},
}


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


class TestSlashCommands:
    async def test_every_command_appears_in_the_slash_list(self, bot: KSBot):
        """`/`를 눌렀을 때 목록에 뜨려면 앱 커맨드로 등록돼 있어야 한다."""
        await bot.load_all_extensions()

        app_names = {command.name for command in bot.tree.get_commands()}
        prefix_names = {command.name for command in bot.commands if not command.hidden}

        # 접두사 전용은 도움말 하나뿐이고, 그건 슬래시 전용 이름으로 따로 등록한다.
        assert prefix_names - app_names == {'help'}

    async def test_help_is_reachable_from_the_slash_list(self, bot: KSBot):
        await bot.load_all_extensions()
        register_help_app_command(bot)

        assert bot.tree.get_command(SLASH_HELP_NAME) is not None

    async def test_registering_help_twice_is_safe(self, bot: KSBot):
        """`setup_hook`이 재연결로 다시 불려도 중복 등록되면 안 된다."""
        await bot.load_all_extensions()
        register_help_app_command(bot)
        register_help_app_command(bot)

        assert sum(1 for c in bot.tree.get_commands() if c.name == SLASH_HELP_NAME) == 1

    async def test_slash_names_are_valid(self, bot: KSBot):
        """디스코드는 앱 커맨드 이름에 대문자·공백을 허용하지 않는다(32자 제한)."""
        await bot.load_all_extensions()
        register_help_app_command(bot)

        for command in bot.tree.walk_commands():
            assert command.name == command.name.lower(), command.name
            assert ' ' not in command.name, command.name
            assert 1 <= len(command.name) <= 32, command.name

    async def test_slash_descriptions_fit_the_limit(self, bot: KSBot):
        """설명이 100자를 넘으면 등록 자체가 거부된다."""
        await bot.load_all_extensions()
        register_help_app_command(bot)

        for command in bot.tree.walk_commands():
            assert 1 <= len(command.description) <= 100, (command.name, len(command.description))


class TestSlashCommandGroups:
    """`/` 목록을 카테고리로 묶은 구조를 고정한다.

    디스코드에는 최상위 커맨드에 붙일 카테고리 개념이 없다. 목록을 묶는 유일한 수단이
    서브커맨드 그룹이므로, 그룹 구조가 무너지면 목록이 다시 27줄로 평평해진다.
    """

    async def test_categories_are_grouped(self, bot: KSBot):
        await bot.load_all_extensions()

        for name, expected in EXPECTED_GROUPS.items():
            group = bot.tree.get_command(name)
            assert isinstance(group, app_commands.Group), f'{name}이(가) 그룹이 아닙니다.'
            assert {command.name for command in group.commands} == expected

    async def test_frequently_used_commands_stay_top_level(self, bot: KSBot):
        """자주 쓰는 커맨드까지 두 단어로 만들면 오히려 불편해진다."""
        await bot.load_all_extensions()
        register_help_app_command(bot)

        for name in ('점수', SLASH_HELP_NAME):
            command = bot.tree.get_command(name)
            assert command is not None, name
            assert not isinstance(command, app_commands.Group), name

    async def test_top_level_list_stays_short(self, bot: KSBot):
        """그룹화의 목적 자체가 목록 길이를 줄이는 것이다."""
        await bot.load_all_extensions()
        register_help_app_command(bot)

        top_level = bot.tree.get_commands()
        executable = sum(len(c.commands) if isinstance(c, app_commands.Group) else 1 for c in top_level)

        assert len(top_level) <= 10
        assert executable > len(top_level)  # 실제 커맨드 수는 그대로여야 한다

    async def test_groups_fit_discord_limits(self, bot: KSBot):
        """그룹당 하위 커맨드는 25개까지고, 중첩은 1단계까지만 허용된다."""
        await bot.load_all_extensions()

        for group in (c for c in bot.tree.get_commands() if isinstance(c, app_commands.Group)):
            assert len(group.commands) <= 25, group.name
            nested = [c for c in group.commands if isinstance(c, app_commands.Group)]
            assert nested == [], f'{group.name} 아래에 그룹이 또 있습니다: {[c.name for c in nested]}'

    async def test_prefix_form_matches_the_slash_form(self, bot: KSBot):
        """`/음악 재생`을 그대로 타이핑해도 동작해야 한다."""
        await bot.load_all_extensions()

        assert bot.get_command('음악 재생') is not None
        assert bot.get_command('유저 추방') is not None
        # 그룹으로 옮겼으므로 옛 최상위 이름은 더 이상 존재하지 않는다.
        assert bot.get_command('재생') is None


class TestBuildGroupHelpEmbed:
    """`/음악`처럼 그룹만 입력했을 때의 안내."""

    async def test_lists_every_subcommand(self, bot: KSBot):
        await bot.load_all_extensions()

        embed = build_group_help_embed(bot.get_command('음악'), '/')
        values = ' '.join(field.value for field in embed.fields)

        for name in EXPECTED_GROUPS['음악']:
            assert f'`/음악 {name}`' in values

    async def test_fits_discord_limits(self, bot: KSBot):
        """음악은 하위 커맨드가 10개라 필드 하나(1024자)를 넘길 수 있다."""
        await bot.load_all_extensions()

        embed = build_group_help_embed(bot.get_command('음악'), '/')

        assert embed.fields  # 기본 구현은 아무것도 보내지 않아 봇이 침묵했다
        assert all(len(field.value) <= 1024 for field in embed.fields)
        assert len(embed) <= 6000


class TestBuildHelpEmbed:
    async def test_lists_every_cog(self, bot: KSBot):
        await bot.load_all_extensions()

        embed = build_help_embed(collect_command_mapping(bot), '/')

        names = ' '.join(field.name for field in embed.fields)
        assert '음악' in names
        assert '밸런서' in names

    async def test_group_commands_show_the_full_path(self, bot: KSBot):
        """`재생`만 보여주면 어떻게 부르는지 알 수 없다."""
        await bot.load_all_extensions()

        embed = build_help_embed(collect_command_mapping(bot), '/')
        values = ' '.join(field.value for field in embed.fields)

        assert '`/음악 재생`' in values
        assert '`/유저 추방`' in values
        # 그룹 자체는 호출할 수 없으므로 목록에 넣지 않는다.
        assert '`/음악`\n' not in values

    async def test_field_values_fit_discord_limit(self, bot: KSBot):
        await bot.load_all_extensions()

        embed = build_help_embed(collect_command_mapping(bot), '/')

        assert all(len(field.value) <= 1024 for field in embed.fields)
        assert len(embed) <= 6000  # 임베드 전체 길이 제한


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

        missing = [command.qualified_name for command in bot.walk_commands() if not command.hidden and not (command.help or command.description)]

        assert missing == []

    async def test_no_alias_collides_with_a_command_name(self, bot: KSBot):
        """별칭 충돌은 같은 부모 아래에서만 문제가 된다."""
        await bot.load_all_extensions()

        names: dict[str, set[str]] = {}
        for command in bot.walk_commands():
            names.setdefault(command.full_parent_name, set()).add(command.name)

        collisions = [
            (command.qualified_name, alias)
            for command in bot.walk_commands()
            for alias in command.aliases
            if alias in names.get(command.full_parent_name, set())
        ]

        assert collisions == []


def test_help_attrs_are_plain_data():
    """`command_attrs`는 discord.py가 그대로 소비하므로 단순 값이어야 한다."""
    assert isinstance(HELP_COMMAND_ATTRS, dict)
    assert all(isinstance(value, (str, list)) for value in HELP_COMMAND_ATTRS.values())
    assert SimpleNamespace(**HELP_COMMAND_ATTRS).name == 'help'
