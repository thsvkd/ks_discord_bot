"""실행 설정.

환경 변수(또는 프로젝트 루트의 `.env`)에서 값을 읽어 검증한다.
설정이 잘못되면 봇이 절반만 동작하는 대신 `ConfigError`로 즉시 실패한다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from ks_bot.common.errors import ConfigError

__all__ = ['PROJECT_ROOT', 'Settings', 'load_dotenv']

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = PROJECT_ROOT / '.env'


def load_dotenv(path: Path = DEFAULT_ENV_FILE) -> None:
    """`.env` 파일을 읽어 환경 변수에 채운다(이미 설정된 값은 덮어쓰지 않는다).

    외부 의존성 없이 `KEY=VALUE` 형식만 지원한다.
    """
    if not path.is_file():
        return

    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _env_str(name: str, default: str = '') -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int) -> int:
    raw = _env_str(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as e:
        raise ConfigError(f'환경 변수 {name}은(는) 정수여야 합니다. 현재 값: {raw!r}') from e


@dataclass(frozen=True)
class Settings:
    """봇 실행에 필요한 모든 설정값."""

    discord_token: str
    pubg_token: str = ''
    pubg_platform: str = 'steam'
    command_prefix: str = '/'
    db_path: Path = field(default=PROJECT_ROOT / 'res' / 'history.db')
    game_result_dir: Path = field(default=PROJECT_ROOT / 'res' / 'game_result')
    log_level: str = 'INFO'
    member_status_interval_minutes: int = 30
    max_match_num: int = 40
    player_cache_ttl_hours: int = 1

    @classmethod
    def from_env(cls, *, require_discord_token: bool = True) -> Settings:
        """환경 변수에서 설정을 로드한다.

        Raises:
            ConfigError: 필수 값이 없거나 형식이 잘못된 경우.
        """
        load_dotenv()

        discord_token = _env_str('DISCORD_TOKEN')
        if require_discord_token and not discord_token:
            raise ConfigError(
                'DISCORD_TOKEN 환경 변수가 설정되지 않았습니다.\n'
                '  - 쉘 설정 파일에 `export DISCORD_TOKEN="your_token_here"` 를 추가하거나\n'
                f'  - 프로젝트 루트({PROJECT_ROOT})에 `.env` 파일을 만들고 `DISCORD_TOKEN=...` 을 적어주세요.'
            )

        db_path = Path(_env_str('KS_BOT_DB_PATH') or (PROJECT_ROOT / 'res' / 'history.db'))
        game_result_dir = Path(_env_str('KS_BOT_GAME_RESULT_DIR') or (PROJECT_ROOT / 'res' / 'game_result'))

        return cls(
            discord_token=discord_token,
            pubg_token=_env_str('PUBG_TOKEN'),
            pubg_platform=_env_str('PUBG_PLATFORM', 'steam'),
            command_prefix=_env_str('KS_BOT_COMMAND_PREFIX', '/'),
            db_path=db_path,
            game_result_dir=game_result_dir,
            log_level=_env_str('KS_BOT_LOG_LEVEL', 'INFO').upper(),
            member_status_interval_minutes=_env_int('KS_BOT_MEMBER_STATUS_INTERVAL_MINUTES', 30),
            max_match_num=_env_int('KS_BOT_MAX_MATCH_NUM', 40),
            player_cache_ttl_hours=_env_int('KS_BOT_PLAYER_CACHE_TTL_HOURS', 1),
        )

    @property
    def has_pubg_token(self) -> bool:
        return bool(self.pubg_token)
