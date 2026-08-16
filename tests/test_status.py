"""scripts/status.py 단위 테스트. 디스코드/호스트에 실제로 접속하지 않는다."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import aiohttp
import pytest

from ks_bot.common.errors import ConfigError
from ks_bot.config import Settings

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / 'scripts'


def load_status():
    spec = importlib.util.spec_from_file_location('ks_bot_status', SCRIPTS_DIR / 'status.py')
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


status = load_status()


class TestFormatters:
    def test_format_bytes(self):
        assert status.format_bytes(512) == '512 B'
        assert status.format_bytes(1024) == '1.0 KiB'
        assert status.format_bytes(5 * 1024 * 1024) == '5.0 MiB'

    def test_format_duration(self):
        assert status.format_duration(30) == '0분'
        assert status.format_duration(90) == '1분'
        assert status.format_duration(3661) == '1시간 1분'
        assert status.format_duration(90000) == '1일 1시간'


class TestProcessMatching:
    def test_matches_console_script(self):
        assert status.is_bot_process('/home/pi/Workspace/ks_discord_bot/.venv/bin/ks-bot')

    def test_matches_module_invocation(self):
        assert status.is_bot_process('python -m ks_bot')
        assert status.is_bot_process('python3 -m ks_bot.__main__')

    def test_matches_main_module_path(self):
        assert status.is_bot_process('python /home/pi/Workspace/ks_discord_bot/ks_bot/__main__.py')
        assert not status.is_bot_process('/home/pi/Workspace/ks_discord_bot/ks_bot/__main__.py')

    def test_matches_compat_main_py_in_this_repo(self, tmp_path: Path):
        assert status.is_bot_process('python main.py', cwd=status.PROJECT_ROOT)
        assert not status.is_bot_process('python main.py', cwd=tmp_path)

    def test_ignores_editors_and_pagers(self):
        assert not status.is_bot_process('nano ks_bot/__main__.py')
        assert not status.is_bot_process('less .venv/bin/ks-bot')
        assert not status.is_bot_process('cat /home/pi/Workspace/ks_discord_bot/ks_bot/__main__.py')

    def test_ignores_status_and_helper_scripts(self):
        assert not status.is_bot_process('uv run python scripts/status.py --local')
        assert not status.is_bot_process('python scripts/send_message.py --list-channels')
        assert not status.is_bot_process('python scripts/preview_giveaways.py --dry-run')

    def test_ignores_pytest_and_repo_path_only(self):
        assert not status.is_bot_process('pytest tests/test_bot.py')
        assert not status.is_bot_process('python /home/pi/Workspace/ks_discord_bot/other.py')

    def test_parse_ps_output_skips_malformed_lines(self):
        text = '\n'.join(
            [
                ' 1234    01:02:03  81920 /home/pi/.venv/bin/ks-bot',
                'not-a-process',
                '',
                ' 99  00:01  abc python -m ks_bot',
            ]
        )
        rows = status.parse_ps_output(text)
        assert len(rows) == 1
        assert rows[0].pid == 1234
        assert rows[0].rss_kib == 81920
        assert rows[0].cmdline.endswith('ks-bot')


class TestSettingsSummary:
    def test_does_not_include_token_value(self, tmp_path: Path):
        env_file = tmp_path / '.env'
        env_file.write_text('DISCORD_TOKEN=super-secret\n', encoding='utf-8')
        settings = Settings(
            discord_token='super-secret',
            pubg_token='pubg-secret',
            giveaway_channel_id=42,
            slash_guild_id=99,
            db_path=tmp_path / 'history.db',
        )
        summary = status.summarize_settings(settings, env_file=env_file)
        rendered = status.format_report(
            status.Report(
                host=status.HostStatus('box', 60, (0.1, 0.2, 0.3), 1024, 512, 2048, 1024),
                processes=(),
                settings=summary,
                discord=None,
            )
        )
        assert 'super-secret' not in rendered
        assert 'pubg-secret' not in rendered
        assert '설정됨' in rendered
        assert '채널 42' in rendered
        assert '길드 99' in rendered

    def test_cli_token_marks_settings_as_present(self, tmp_path: Path):
        settings = Settings(discord_token='', db_path=tmp_path / 'history.db')
        summary = status.summarize_settings(settings, env_file=tmp_path / 'missing.env', has_discord_token=True)
        assert summary.discord_token is True


class TestDiscordParsing:
    def test_parse_guilds_and_filter_invalid(self):
        guilds = status.parse_guilds(
            [
                {
                    'id': '111',
                    'name': '클랜',
                    'approximate_member_count': 24,
                    'approximate_presence_count': 8,
                    'owner': True,
                },
                {'name': 'id 없음'},
                'skip-me',
            ]
        )
        assert len(guilds) == 1
        assert guilds[0].id == 111
        assert guilds[0].member_count == 24
        assert guilds[0].owner is True

    def test_describe_http_error(self):
        assert '토큰' in status.describe_http_error(401)
        assert '레이트' in status.describe_http_error(429)
        assert 'HTTP 500' in status.describe_http_error(500)

    async def test_collect_discord_success(self):
        async def get_json(method: str, url: str):
            assert method == 'GET'
            if url.endswith('/users/@me'):
                return 200, {'id': '1', 'username': 'KSBot', 'discriminator': '0'}, 12.5
            if 'guilds' in url:
                return 200, [{'id': '10', 'name': '서버', 'approximate_member_count': 3, 'owner': False}], 8.0
            if url.endswith('/channels/77'):
                return 200, {'id': '77', 'name': '무료게임'}, 4.0
            raise AssertionError(url)

        result = await status.collect_discord('token', giveaway_channel_id=77, get_json=get_json)
        assert result.ok is True
        assert result.user == 'KSBot'
        assert result.user_id == 1
        assert result.guilds[0].name == '서버'
        assert result.guild_count == 1
        assert result.giveaway_channel == '#무료게임 (77)'

    async def test_collect_discord_unauthorized(self):
        async def get_json(method: str, url: str):
            return 401, {'message': '401: Unauthorized'}, 3.0

        result = await status.collect_discord('bad', get_json=get_json)
        assert result.ok is False
        assert '토큰' in result.error

    async def test_collect_discord_filters_guild(self):
        async def get_json(method: str, url: str):
            if url.endswith('/users/@me'):
                return 200, {'id': '1', 'username': 'KSBot', 'discriminator': '0'}, 1.0
            return (
                200,
                [
                    {'id': '10', 'name': 'A'},
                    {'id': '20', 'name': 'B'},
                ],
                1.0,
            )

        result = await status.collect_discord('token', guild_id=20, get_json=get_json)
        assert [guild.id for guild in result.guilds] == [20]
        assert result.guild_count == 2
        assert result.guild_filter_miss is False

    async def test_collect_discord_missing_guild_filter(self):
        async def get_json(method: str, url: str):
            if url.endswith('/users/@me'):
                return 200, {'id': '1', 'username': 'KSBot', 'discriminator': '0'}, 1.0
            return 200, [{'id': '10', 'name': 'A'}], 1.0

        result = await status.collect_discord('token', guild_id=99, get_json=get_json)
        assert result.ok is True
        assert result.guild_count == 1
        assert result.guilds == ()
        assert result.guild_filter_miss is True
        rendered = status.format_report(
            status.Report(
                host=status.HostStatus('box', None, None, None, None, None, None),
                processes=(),
                settings=status.summarize_settings(Settings(discord_token='x', db_path=Path('/tmp/x.db')), env_file=Path('/tmp/x.env')),
                discord=result,
            )
        )
        assert '지정한 길드 99' in rendered
        assert '초대 링크' not in rendered

    async def test_collect_discord_later_request_error(self):
        async def get_json(method: str, url: str):
            if url.endswith('/users/@me'):
                return 200, {'id': '1', 'username': 'KSBot', 'discriminator': '0'}, 1.0
            raise aiohttp.ClientConnectionError()

        result = await status.collect_discord('token', get_json=get_json)
        assert result.ok is False
        assert '연결하지 못했습니다' in result.error


class TestReport:
    def test_check_failed_when_process_missing(self):
        report = status.Report(
            host=status.HostStatus('box', None, None, None, None, None, None),
            processes=(),
            settings=status.summarize_settings(
                Settings(discord_token='', db_path=Path('/tmp/missing.db')),
                env_file=Path('/tmp/missing.env'),
            ),
            discord=status.DiscordStatus(ok=True, user='bot'),
        )
        assert status.check_failed(report) is True

    def test_check_failed_when_discord_fails(self):
        report = status.Report(
            host=status.HostStatus('box', None, None, None, None, None, None),
            processes=(status.ProcessInfo(1, '00:01', 100, 'ks-bot'),),
            settings=status.summarize_settings(
                Settings(discord_token='x', db_path=Path('/tmp/missing.db')),
                env_file=Path('/tmp/missing.env'),
            ),
            discord=status.DiscordStatus(ok=False, error='down'),
        )
        assert status.check_failed(report) is True

    def test_format_report_offline_process(self):
        rendered = status.format_report(
            status.Report(
                host=status.HostStatus('pi5', 120, (0.1, 0.1, 0.1), 1024, 512, 4096, 1024),
                processes=(),
                settings=status.summarize_settings(
                    Settings(discord_token='', db_path=Path('/tmp/missing.db')),
                    env_file=Path('/tmp/missing.env'),
                ),
                discord=None,
            )
        )
        assert '실행 중이지 않음' in rendered
        assert '건너뜀' in rendered
        assert 'pi5' in rendered

    def test_parse_args_local_and_check(self):
        args = status.parse_args(['--local', '--check', '--guild-id', '5'])
        assert args.local is True
        assert args.check is True
        assert args.guild_id == 5

    def test_check_ok_when_process_and_discord_are_healthy(self):
        report = status.Report(
            host=status.HostStatus('box', None, None, None, None, None, None),
            processes=(status.ProcessInfo(1, '00:01', 100, 'ks-bot'),),
            settings=status.summarize_settings(
                Settings(discord_token='x', db_path=Path('/tmp/missing.db')),
                env_file=Path('/tmp/missing.env'),
            ),
            discord=status.DiscordStatus(ok=True, user='bot'),
        )
        assert status.check_failed(report) is False

    def test_check_failed_when_ps_unreadable(self):
        report = status.Report(
            host=status.HostStatus('box', None, None, None, None, None, None),
            processes=(),
            settings=status.summarize_settings(
                Settings(discord_token='x', db_path=Path('/tmp/missing.db')),
                env_file=Path('/tmp/missing.env'),
            ),
            discord=status.DiscordStatus(ok=True, user='bot'),
            process_error='ps failed',
        )
        assert status.check_failed(report) is True
        assert '확인 불가' in status.format_report(report)

    def test_redacts_secrets_in_cmdline(self):
        assert status.redact_cmdline('DISCORD_TOKEN=super-secret python -m ks_bot') == 'DISCORD_TOKEN=*** python -m ks_bot'
        assert status.redact_cmdline('python scripts/status.py --token super-secret') == 'python scripts/status.py --token ***'


class TestMainLocal:
    def test_local_check_exits_1_when_bot_is_down(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(status, 'collect_host', lambda: status.HostStatus('box', 1, (0, 0, 0), 2, 1, 4, 1))
        monkeypatch.setattr(status, 'collect_processes', lambda: status.ProcessSnapshot())
        monkeypatch.setattr(
            status.Settings,
            'from_env',
            classmethod(lambda cls, **kwargs: Settings(discord_token='', db_path=Path('/tmp/x.db'))),
        )
        assert status.main(['--local', '--check']) == 1

    def test_local_check_exits_0_when_bot_is_up(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(status, 'collect_host', lambda: status.HostStatus('box', 1, (0, 0, 0), 2, 1, 4, 1))
        monkeypatch.setattr(
            status,
            'collect_processes',
            lambda: status.ProcessSnapshot((status.ProcessInfo(9, '00:01', 100, '/venv/bin/ks-bot'),)),
        )
        monkeypatch.setattr(
            status.Settings,
            'from_env',
            classmethod(lambda cls, **kwargs: Settings(discord_token='', db_path=Path('/tmp/x.db'))),
        )
        assert status.main(['--local', '--check']) == 0

    def test_config_error_still_prints_host(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
        monkeypatch.setattr(status, 'collect_host', lambda: status.HostStatus('box', 1, (0, 0, 0), 2, 1, 4, 1))
        monkeypatch.setattr(status, 'collect_processes', lambda: status.ProcessSnapshot())

        def boom(cls, **kwargs):
            raise ConfigError('KS_BOT_MAX_MATCH_NUM은(는) 정수여야 합니다.')

        monkeypatch.setattr(status.Settings, 'from_env', classmethod(boom))
        assert status.main(['--local']) == 0
        output = capsys.readouterr().out
        assert 'box' in output
        assert '정수여야' in output
