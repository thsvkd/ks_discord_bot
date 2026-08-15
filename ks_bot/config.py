"""실행 설정.

환경 변수(또는 프로젝트 루트의 `.env`)에서 값을 읽어 검증한다.
설정이 잘못되면 봇이 절반만 동작하는 대신 `ConfigError`로 즉시 실패한다.
"""

from __future__ import annotations

import codecs
import os
from dataclasses import dataclass, field
from pathlib import Path

from ks_bot.common.errors import ConfigError
from ks_bot.common.giveaway import Store

__all__ = ['PROJECT_ROOT', 'Settings', 'load_dotenv', 'parse_dotenv', 'read_env_text']

# 무료 배포 알림에서 기본으로 다룰 스토어.
# itch.io는 소규모 인디 무료 배포가 대량으로 올라와 알림이 묻히기 쉬워 기본값에서 제외한다.
DEFAULT_GIVEAWAY_STORES = (Store.STEAM, Store.EPIC, Store.GOG)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = PROJECT_ROOT / '.env'


def read_env_text(path: Path) -> str:
    """`.env` 파일을 텍스트로 읽는다.

    윈도우 PowerShell의 `>>`/`Add-Content`는 기본적으로 UTF-16LE로 덧붙이기 때문에
    UTF-8 파일에 UTF-16 구간이 섞이는 일이 흔하다. 이 경우 문자 사이에 NUL이 끼는데,
    그대로 파싱하면 키 이름이 `D\\x00I\\x00S...` 형태가 되어 값을 못 읽는다.
    NUL을 제거해 두 인코딩이 섞인 파일도 읽을 수 있게 한다.
    """
    raw = path.read_bytes()
    if raw.startswith(codecs.BOM_UTF16_LE) or raw.startswith(codecs.BOM_UTF16_BE):
        return raw.decode('utf-16')
    return raw.decode('utf-8-sig', errors='replace').replace('\x00', '')


def parse_dotenv(text: str) -> dict[str, str]:
    """`KEY=VALUE` 형식을 파싱한다. 같은 키가 여러 번 나오면 마지막 값을 쓴다.

    값이 비어 있는 항목은 무시한다. (템플릿에 남아 있는 `KEY=` 줄이
    아래쪽의 실제 값을 가리는 사고를 막는다.)
    """
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip('﻿')
        if not line or line.startswith('#') or '=' not in line:
            continue

        key, _, value = line.partition('=')
        key = key.strip()
        if key.lower().startswith('export '):
            key = key[len('export ') :].strip()
        value = value.strip().strip('"').strip("'")

        if key and value:
            values[key] = value
    return values


def load_dotenv(path: Path = DEFAULT_ENV_FILE) -> None:
    """`.env` 파일을 읽어 환경 변수에 채운다(이미 설정된 값은 덮어쓰지 않는다)."""
    if not path.is_file():
        return

    for key, value in parse_dotenv(read_env_text(path)).items():
        os.environ.setdefault(key, value)


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


_TRUE_VALUES = frozenset({'1', 'true', 'yes', 'y', 'on'})
_FALSE_VALUES = frozenset({'0', 'false', 'no', 'n', 'off'})


def _env_bool(name: str, default: bool) -> bool:
    raw = _env_str(name).lower()
    if not raw:
        return default
    if raw in _TRUE_VALUES:
        return True
    if raw in _FALSE_VALUES:
        return False
    raise ConfigError(f'환경 변수 {name}은(는) true/false여야 합니다. 현재 값: {raw!r}')


def _env_stores(name: str, default: tuple[Store, ...]) -> tuple[Store, ...]:
    """`steam,epic,gog` 형태의 목록을 파싱한다.

    오타를 조용히 무시하면 알림이 통째로 사라지므로, 모르는 이름은 즉시 오류로 알린다.
    """
    raw = _env_str(name)
    if not raw:
        return default

    stores: list[Store] = []
    for token in raw.split(','):
        name_token = token.strip().lower()
        if not name_token:
            continue
        try:
            store = Store(name_token)
        except ValueError as e:
            allowed = ', '.join(sorted(item.value for item in Store))
            raise ConfigError(f'환경 변수 {name}에 알 수 없는 스토어가 있습니다: {name_token!r} (가능한 값: {allowed})') from e
        if store not in stores:
            stores.append(store)
    return tuple(stores) or default


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
    giveaway_channel_id: int = 0
    giveaway_interval_minutes: int = 30
    giveaway_stores: tuple[Store, ...] = DEFAULT_GIVEAWAY_STORES
    giveaway_mention_role_id: int = 0
    giveaway_include_upcoming: bool = True
    slash_guild_id: int = 0

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
            giveaway_channel_id=_env_int('KS_BOT_GIVEAWAY_CHANNEL_ID', 0),
            giveaway_interval_minutes=_env_int('KS_BOT_GIVEAWAY_INTERVAL_MINUTES', 30),
            giveaway_stores=_env_stores('KS_BOT_GIVEAWAY_STORES', DEFAULT_GIVEAWAY_STORES),
            giveaway_mention_role_id=_env_int('KS_BOT_GIVEAWAY_MENTION_ROLE_ID', 0),
            giveaway_include_upcoming=_env_bool('KS_BOT_GIVEAWAY_INCLUDE_UPCOMING', True),
            slash_guild_id=_env_int('KS_BOT_SLASH_GUILD_ID', 0),
        )

    @property
    def has_pubg_token(self) -> bool:
        return bool(self.pubg_token)

    @property
    def has_giveaway_channel(self) -> bool:
        return self.giveaway_channel_id > 0
