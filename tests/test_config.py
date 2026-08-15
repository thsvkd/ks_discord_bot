"""설정 로딩 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from ks_bot.common.errors import ConfigError
from ks_bot.config import Settings, load_dotenv

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
