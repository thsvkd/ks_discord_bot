"""설정 로딩 테스트."""

from __future__ import annotations

import codecs
from pathlib import Path

import pytest

from ks_bot.common.errors import ConfigError
from ks_bot.common.giveaway import Store
from ks_bot.config import PROJECT_ROOT, Settings, load_dotenv, parse_dotenv, read_env_text

_ENV_KEYS = (
    'DISCORD_TOKEN',
    'PUBG_TOKEN',
    'PUBG_PLATFORM',
    'KS_BOT_COMMAND_PREFIX',
    'KS_BOT_DB_PATH',
    'KS_BOT_GAME_RESULT_DIR',
    'KS_BOT_LOG_LEVEL',
    'KS_BOT_MEMBER_STATUS_INTERVAL_MINUTES',
    'KS_BOT_MAX_MATCH_NUM',
    'KS_BOT_PLAYER_CACHE_TTL_HOURS',
    'KS_BOT_GIVEAWAY_CHANNEL_ID',
    'KS_BOT_GIVEAWAY_INTERVAL_MINUTES',
    'KS_BOT_GIVEAWAY_STORES',
    'KS_BOT_GIVEAWAY_MENTION_ROLE_ID',
    'KS_BOT_GIVEAWAY_INCLUDE_UPCOMING',
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    # `.env` 파일이 테스트 결과에 영향을 주지 않도록 로딩을 비활성화한다.
    monkeypatch.setattr('ks_bot.config.load_dotenv', lambda *args, **kwargs: None)


class TestFromEnv:
    def test_missing_token_raises(self):
        with pytest.raises(ConfigError) as exc_info:
            Settings.from_env()
        assert 'DISCORD_TOKEN' in exc_info.value.message

    def test_token_can_be_optional(self):
        assert Settings.from_env(require_discord_token=False).discord_token == ''

    def test_defaults(self, monkeypatch):
        monkeypatch.setenv('DISCORD_TOKEN', 'token')
        settings = Settings.from_env()

        assert settings.command_prefix == '/'
        assert settings.pubg_platform == 'steam'
        assert settings.log_level == 'INFO'
        assert settings.member_status_interval_minutes == 30
        assert settings.has_pubg_token is False

    def test_overrides(self, monkeypatch):
        monkeypatch.setenv('DISCORD_TOKEN', 'token')
        monkeypatch.setenv('PUBG_TOKEN', 'pubg')
        monkeypatch.setenv('KS_BOT_COMMAND_PREFIX', '!')
        monkeypatch.setenv('KS_BOT_LOG_LEVEL', 'debug')
        monkeypatch.setenv('KS_BOT_MAX_MATCH_NUM', '10')

        settings = Settings.from_env()

        assert settings.command_prefix == '!'
        assert settings.log_level == 'DEBUG'
        assert settings.max_match_num == 10
        assert settings.has_pubg_token is True

    def test_invalid_integer_raises(self, monkeypatch):
        monkeypatch.setenv('DISCORD_TOKEN', 'token')
        monkeypatch.setenv('KS_BOT_MAX_MATCH_NUM', '많이')

        with pytest.raises(ConfigError):
            Settings.from_env()


class TestGiveawayStores:
    def test_default_stores(self, monkeypatch):
        monkeypatch.setenv('DISCORD_TOKEN', 'token')
        assert Settings.from_env().giveaway_stores == (Store.STEAM, Store.EPIC, Store.GOG)

    def test_parses_list(self, monkeypatch):
        monkeypatch.setenv('DISCORD_TOKEN', 'token')
        monkeypatch.setenv('KS_BOT_GIVEAWAY_STORES', ' steam , itch ,steam, ')

        assert Settings.from_env().giveaway_stores == (Store.STEAM, Store.ITCH)

    def test_unknown_store_raises(self, monkeypatch):
        """오타를 조용히 무시하면 알림이 통째로 사라진다."""
        monkeypatch.setenv('DISCORD_TOKEN', 'token')
        monkeypatch.setenv('KS_BOT_GIVEAWAY_STORES', 'steam,스팀')

        with pytest.raises(ConfigError) as exc_info:
            Settings.from_env()
        assert '스팀' in exc_info.value.message

    def test_every_store_is_documented_in_env_example(self):
        """`.env.example`이 실제 선택지와 어긋나면 사용자가 값을 알 수 없다."""
        example = (PROJECT_ROOT / '.env.example').read_text(encoding='utf-8')

        missing = [store.value for store in Store if store.value not in example]
        assert missing == []

    def test_env_example_store_list_is_parsable(self, monkeypatch):
        """예시로 적어둔 '전부 받기' 줄이 실제로 파싱되는지 확인한다."""
        example = (PROJECT_ROOT / '.env.example').read_text(encoding='utf-8')
        line = next(line for line in example.splitlines() if 'KS_BOT_GIVEAWAY_STORES=' in line and 'other' in line)

        monkeypatch.setenv('DISCORD_TOKEN', 'token')
        monkeypatch.setenv('KS_BOT_GIVEAWAY_STORES', line.split('=', 1)[1])

        assert set(Settings.from_env().giveaway_stores) == set(Store)


class TestDotenv:
    def test_load_dotenv_sets_missing_keys(self, tmp_path: Path, monkeypatch):
        env_file = tmp_path / '.env'
        env_file.write_text('# 주석\nDISCORD_TOKEN="from-file"\nEMPTY_LINE_FOLLOWS=1\n\n', encoding='utf-8')
        monkeypatch.delenv('DISCORD_TOKEN', raising=False)

        load_dotenv(env_file)

        import os

        assert os.environ['DISCORD_TOKEN'] == 'from-file'
        assert os.environ['EMPTY_LINE_FOLLOWS'] == '1'
        monkeypatch.delenv('EMPTY_LINE_FOLLOWS', raising=False)

    def test_existing_env_wins(self, tmp_path: Path, monkeypatch):
        env_file = tmp_path / '.env'
        env_file.write_text('DISCORD_TOKEN=from-file\n', encoding='utf-8')
        monkeypatch.setenv('DISCORD_TOKEN', 'from-shell')

        load_dotenv(env_file)

        import os

        assert os.environ['DISCORD_TOKEN'] == 'from-shell'

    def test_missing_file_is_ignored(self, tmp_path: Path):
        load_dotenv(tmp_path / 'nope.env')


class TestDotenvParsing:
    def test_last_value_wins_and_empty_is_ignored(self):
        """템플릿에 남은 `KEY=` 빈 줄이 아래쪽 실제 값을 가리면 안 된다."""
        parsed = parse_dotenv('DISCORD_TOKEN=\nPUBG_TOKEN=abc\nDISCORD_TOKEN=real-token\n')

        assert parsed == {'PUBG_TOKEN': 'abc', 'DISCORD_TOKEN': 'real-token'}

    def test_quotes_and_export_prefix(self):
        parsed = parse_dotenv('export DISCORD_TOKEN="quoted"\nPUBG_TOKEN=\'single\'\n')

        assert parsed == {'DISCORD_TOKEN': 'quoted', 'PUBG_TOKEN': 'single'}

    def test_comments_and_malformed_lines_are_skipped(self):
        assert parse_dotenv('# 주석\n\n형식이상\nKEY=value\n') == {'KEY': 'value'}

    def test_value_containing_equals_sign(self):
        assert parse_dotenv('TOKEN=a=b=c\n') == {'TOKEN': 'a=b=c'}

    def test_utf16_appended_section_is_readable(self, tmp_path: Path):
        """PowerShell `>>`로 덧붙이면 UTF-8 파일에 UTF-16LE 구간이 섞인다."""
        env_file = tmp_path / '.env'
        env_file.write_bytes(b'# comment\nPUBG_TOKEN=utf8-value\n' + 'DISCORD_TOKEN=utf16-value\n'.encode('utf-16-le'))

        parsed = parse_dotenv(read_env_text(env_file))

        assert parsed == {'PUBG_TOKEN': 'utf8-value', 'DISCORD_TOKEN': 'utf16-value'}

    def test_utf16_file_with_bom(self, tmp_path: Path):
        env_file = tmp_path / '.env'
        env_file.write_bytes(codecs.BOM_UTF16_LE + 'DISCORD_TOKEN=bom-value\n'.encode('utf-16-le'))

        assert parse_dotenv(read_env_text(env_file)) == {'DISCORD_TOKEN': 'bom-value'}

    def test_utf8_bom_is_stripped(self, tmp_path: Path):
        env_file = tmp_path / '.env'
        env_file.write_bytes(codecs.BOM_UTF8 + b'DISCORD_TOKEN=value\n')

        assert parse_dotenv(read_env_text(env_file)) == {'DISCORD_TOKEN': 'value'}
