"""봇이 떠 있는 서버와 디스코드 접속 상태를 확인한다.

호스트 자원, 로컬 프로세스, 설정, 디스코드 REST 상태를 한 번에 보여준다.
게이트웨이에 붙지 않으므로, 이미 실행 중인 봇 세션을 끊지 않는다.

사용법:
    python scripts/status.py           # 전체 점검
    python scripts/status.py --local   # 호스트/프로세스/설정만
    python scripts/status.py --check   # 봇 프로세스·디스코드 중 하나라도 실패하면 종료 코드 1
"""

from __future__ import annotations

import argparse
import asyncio
import os
import socket
import subprocess
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp

# 저장소 어디에서 실행해도 `ks_bot` 패키지를 찾을 수 있게 한다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ks_bot.common.errors import ConfigError
from ks_bot.config import PROJECT_ROOT, Settings
from ks_bot.logging_config import get_logger, setup_logging

logger = get_logger('status')

DISCORD_API = 'https://discord.com/api/v10'
USER_AGENT = 'KS-Bot (https://github.com/thsvkd/ks_discord_bot, 0.2.0)'

JsonGetter = Callable[[str, str], Awaitable[tuple[int, Any, float]]]


_VIEWERS = frozenset(
    {
        'awk',
        'bat',
        'cat',
        'chmod',
        'chown',
        'code',
        'cp',
        'emacs',
        'file',
        'git',
        'grep',
        'head',
        'hexdump',
        'less',
        'ls',
        'more',
        'mv',
        'nano',
        'nvim',
        'rg',
        'rm',
        'sed',
        'stat',
        'strings',
        'tail',
        'vi',
        'vim',
    }
)


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    etime: str
    rss_kib: int
    cmdline: str


@dataclass(frozen=True)
class ProcessSnapshot:
    items: tuple[ProcessInfo, ...] = ()
    error: str = ''


@dataclass(frozen=True)
class HostStatus:
    hostname: str
    uptime_seconds: float | None
    loadavg: tuple[float, float, float] | None
    mem_total: int | None
    mem_available: int | None
    disk_total: int | None
    disk_used: int | None


@dataclass(frozen=True)
class SettingsSummary:
    env_file: bool
    discord_token: bool
    pubg: bool
    giveaway_channel_id: int
    slash_guild_id: int
    command_prefix: str
    log_level: str
    db_path: Path
    db_exists: bool


@dataclass(frozen=True)
class GuildStatus:
    id: int
    name: str
    member_count: int | None
    presence_count: int | None
    owner: bool


@dataclass(frozen=True)
class DiscordStatus:
    ok: bool
    user: str = ''
    user_id: int = 0
    latency_ms: float | None = None
    guilds: tuple[GuildStatus, ...] = ()
    giveaway_channel: str = ''
    error: str = ''
    guild_count: int = 0
    guild_filter: int | None = None
    guild_filter_miss: bool = False


@dataclass(frozen=True)
class Report:
    host: HostStatus
    processes: tuple[ProcessInfo, ...]
    settings: SettingsSummary
    discord: DiscordStatus | None
    process_error: str = ''
    config_error: str = ''


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='봇 프로세스와 디스코드 서버 상태를 확인합니다.')
    parser.add_argument('--local', action='store_true', help='디스코드 API를 호출하지 않고 호스트/프로세스/설정만 출력합니다.')
    parser.add_argument('--token', default=None, help='봇 토큰 (생략 시 DISCORD_TOKEN 환경 변수 또는 .env 사용)')
    parser.add_argument('--guild-id', type=int, default=None, help='이 서버(길드)만 자세히 표시합니다.')
    parser.add_argument(
        '--check',
        action='store_true',
        help='봇 프로세스가 없거나 디스코드 조회가 실패하면 종료 코드 1을 반환합니다.',
    )
    return parser.parse_args(argv)


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ('B', 'KiB', 'MiB', 'GiB'):
        if value < 1024:
            if unit == 'B':
                return f'{int(value)} {unit}'
            return f'{value:.1f} {unit}'
        value /= 1024
    return f'{value:.1f} TiB'


def format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _secs = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f'{days}일')
    if hours:
        parts.append(f'{hours}시간')
    if minutes or not parts:
        parts.append(f'{minutes}분')
    return ' '.join(parts)


def _is_python_executable(name: str) -> bool:
    base = name.lower()
    return base == 'python' or base.startswith(('python3', 'pypy'))


def redact_cmdline(cmdline: str) -> str:
    """프로세스 명령줄에 섞여 있을 수 있는 토큰 값을 가린다."""
    tokens = cmdline.split()
    redacted: list[str] = []
    hide_next = False
    for token in tokens:
        if hide_next:
            redacted.append('***')
            hide_next = False
            continue
        if token in {'--token', '-t'}:
            redacted.append(token)
            hide_next = True
            continue
        masked = token
        for prefix in ('DISCORD_TOKEN=', 'PUBG_TOKEN='):
            if token.startswith(prefix) or token.upper().startswith(prefix):
                masked = f'{prefix}***'
                break
        redacted.append(masked)
    return ' '.join(redacted)


def is_bot_process(cmdline: str, cwd: Path | None = None) -> bool:
    """이 저장소의 봇 본체 프로세스인지 판별한다.

    편집기/페이저가 소스 경로를 연 경우, 점검 스크립트, pytest는 제외한다.
    프로그램이 `ks-bot` 이거나, 파이썬이 `-m ks_bot` / `__main__.py` / 이 저장소의 `main.py`를
    실행하는 경우만 봇으로 본다.
    """
    normalized = ' '.join(cmdline.replace('\x00', ' ').replace('\\', '/').split())
    if not normalized:
        return False

    lowered = normalized.lower()
    excluded = (
        'scripts/status.py',
        'scripts/send_message.py',
        'scripts/preview_giveaways.py',
        'pytest',
        'ruff ',
        'ruff.exe',
    )
    if any(fragment in lowered for fragment in excluded):
        return False

    tokens = normalized.split()
    if Path(tokens[0]).name.lower() in _VIEWERS:
        return False

    names = [Path(token).name for token in tokens]
    if 'ks-bot' in names:
        return True

    if any(token == '-m' and tokens[index + 1] in {'ks_bot', 'ks_bot.__main__'} for index, token in enumerate(tokens[:-1])):
        return True

    if not any(_is_python_executable(name) for name in names):
        return False

    project_main = (PROJECT_ROOT / 'main.py').resolve()
    for token in tokens:
        if token.endswith(('ks_bot/__main__.py', 'ks_bot/__main__.pyc')):
            return True
        script = Path(token)
        if script.name != 'main.py':
            continue
        if not script.is_absolute() and cwd is not None:
            script = cwd / script
        try:
            if script.resolve() == project_main:
                return True
        except OSError:
            if token.endswith('ks_discord_bot/main.py'):
                return True
    return False


def parse_ps_output(text: str) -> list[ProcessInfo]:
    """`ps -eo pid=,etime=,rss=,args=` 출력을 파싱한다."""
    rows: list[ProcessInfo] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        try:
            rows.append(
                ProcessInfo(
                    pid=int(parts[0]),
                    etime=parts[1],
                    rss_kib=int(parts[2]),
                    cmdline=parts[3],
                )
            )
        except ValueError:
            continue
    return rows


def _process_cwd(pid: int) -> Path | None:
    try:
        return Path(os.readlink(f'/proc/{pid}/cwd'))
    except OSError:
        return None


def collect_processes() -> ProcessSnapshot:
    try:
        completed = subprocess.run(
            ['ps', '-eo', 'pid=,etime=,rss=,args='],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as e:
        logger.warning('프로세스 목록을 읽지 못했습니다: %s', e)
        return ProcessSnapshot(error=str(e))
    items = tuple(proc for proc in parse_ps_output(completed.stdout) if is_bot_process(proc.cmdline, cwd=_process_cwd(proc.pid)))
    return ProcessSnapshot(items=items)


def _read_uptime() -> float | None:
    try:
        return float(Path('/proc/uptime').read_text(encoding='utf-8').split()[0])
    except (OSError, ValueError, IndexError):
        return None


def _read_loadavg() -> tuple[float, float, float] | None:
    try:
        parts = Path('/proc/loadavg').read_text(encoding='utf-8').split()
        return float(parts[0]), float(parts[1]), float(parts[2])
    except (OSError, ValueError, IndexError):
        try:
            return os.getloadavg()
        except OSError:
            return None


def _read_meminfo() -> tuple[int | None, int | None]:
    try:
        values: dict[str, int] = {}
        for raw_line in Path('/proc/meminfo').read_text(encoding='utf-8').splitlines():
            if ':' not in raw_line:
                continue
            key, _, rest = raw_line.partition(':')
            number = rest.strip().split()[0]
            values[key] = int(number) * 1024
        return values.get('MemTotal'), values.get('MemAvailable')
    except (OSError, ValueError, IndexError):
        return None, None


def collect_host(root: Path = PROJECT_ROOT) -> HostStatus:
    mem_total, mem_available = _read_meminfo()
    disk_total = disk_used = None
    try:
        usage = os.statvfs(root)
        disk_total = usage.f_frsize * usage.f_blocks
        disk_used = disk_total - usage.f_frsize * usage.f_bavail
    except OSError:
        pass

    return HostStatus(
        hostname=socket.gethostname(),
        uptime_seconds=_read_uptime(),
        loadavg=_read_loadavg(),
        mem_total=mem_total,
        mem_available=mem_available,
        disk_total=disk_total,
        disk_used=disk_used,
    )


def summarize_settings(
    settings: Settings,
    *,
    env_file: Path | None = None,
    has_discord_token: bool | None = None,
) -> SettingsSummary:
    env_path = PROJECT_ROOT / '.env' if env_file is None else env_file
    token_set = bool(settings.discord_token) if has_discord_token is None else has_discord_token
    return SettingsSummary(
        env_file=env_path.is_file(),
        discord_token=token_set,
        pubg=settings.has_pubg_token,
        giveaway_channel_id=settings.giveaway_channel_id,
        slash_guild_id=settings.slash_guild_id,
        command_prefix=settings.command_prefix,
        log_level=settings.log_level,
        db_path=settings.db_path,
        db_exists=settings.db_path.is_file(),
    )


def describe_http_error(status: int) -> str:
    if status == 401:
        return '봇 토큰이 올바르지 않습니다.'
    if status == 403:
        return '디스코드 API가 권한을 거부했습니다.'
    if status == 429:
        return '디스코드 API 레이트 리밋에 걸렸습니다. 잠시 후 다시 시도하세요.'
    return f'디스코드 API가 HTTP {status}를 반환했습니다.'


async def _default_get_json(method: str, url: str, *, token: str, session: aiohttp.ClientSession) -> tuple[int, Any, float]:
    headers = {
        'Authorization': f'Bot {token}',
        'User-Agent': USER_AGENT,
        'Accept': 'application/json',
    }
    started = time.perf_counter()
    async with session.request(method, url, headers=headers) as response:
        payload: Any
        if response.content_type and 'json' in response.content_type:
            payload = await response.json(content_type=None)
        else:
            payload = await response.text()
        elapsed_ms = (time.perf_counter() - started) * 1000
        return response.status, payload, elapsed_ms


def _as_int(value: Any) -> int | None:
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_guilds(payload: Any) -> list[GuildStatus]:
    if not isinstance(payload, list):
        return []
    guilds: list[GuildStatus] = []
    for item in payload:
        if not isinstance(item, dict) or 'id' not in item:
            continue
        guild_id = _as_int(item.get('id'))
        if guild_id is None:
            continue
        guilds.append(
            GuildStatus(
                id=guild_id,
                name=str(item.get('name') or '(이름 없음)'),
                member_count=_as_int(item.get('approximate_member_count')),
                presence_count=_as_int(item.get('approximate_presence_count')),
                owner=bool(item.get('owner')),
            )
        )
    return guilds


async def collect_discord(
    token: str,
    *,
    giveaway_channel_id: int = 0,
    guild_id: int | None = None,
    get_json: JsonGetter | None = None,
) -> DiscordStatus:
    """디스코드 REST만 호출한다. 게이트웨이 세션을 만들지 않는다."""

    async def run_with(fetch: JsonGetter) -> DiscordStatus:
        try:
            me_status, me_body, latency_ms = await fetch('GET', f'{DISCORD_API}/users/@me')
            if me_status != 200 or not isinstance(me_body, dict):
                return DiscordStatus(ok=False, error=describe_http_error(me_status))

            username = str(me_body.get('username') or '?')
            discriminator = str(me_body.get('discriminator') or '0')
            user = username if discriminator in {'0', '0000'} else f'{username}#{discriminator}'
            user_id = _as_int(me_body.get('id')) or 0

            guilds_status, guilds_body, _ = await fetch('GET', f'{DISCORD_API}/users/@me/guilds?with_counts=true')
            if guilds_status != 200:
                return DiscordStatus(
                    ok=False,
                    user=user,
                    user_id=user_id,
                    latency_ms=latency_ms,
                    error=describe_http_error(guilds_status),
                )

            all_guilds = parse_guilds(guilds_body)
            displayed = [guild for guild in all_guilds if guild.id == guild_id] if guild_id is not None else all_guilds
            filter_miss = guild_id is not None and not displayed

            giveaway_label = ''
            if giveaway_channel_id > 0:
                ch_status, ch_body, _ = await fetch('GET', f'{DISCORD_API}/channels/{giveaway_channel_id}')
                if ch_status == 200 and isinstance(ch_body, dict):
                    name = ch_body.get('name') or giveaway_channel_id
                    giveaway_label = f'#{name} ({giveaway_channel_id})'
                elif ch_status == 404:
                    giveaway_label = f'채널을 찾을 수 없음 ({giveaway_channel_id})'
                elif ch_status == 403:
                    giveaway_label = f'채널 조회 권한 없음 ({giveaway_channel_id})'
                else:
                    giveaway_label = f'조회 실패 HTTP {ch_status} ({giveaway_channel_id})'

            return DiscordStatus(
                ok=True,
                user=user,
                user_id=user_id,
                latency_ms=latency_ms,
                guilds=tuple(displayed),
                giveaway_channel=giveaway_label,
                guild_count=len(all_guilds),
                guild_filter=guild_id,
                guild_filter_miss=filter_miss,
            )
        except (aiohttp.ClientError, TimeoutError) as e:
            return DiscordStatus(ok=False, error=f'디스코드 API에 연결하지 못했습니다: {e}')

    if get_json is not None:
        return await run_with(get_json)

    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:

        async def fetch(method: str, url: str) -> tuple[int, Any, float]:
            return await _default_get_json(method, url, token=token, session=session)

        return await run_with(fetch)


def _flag(enabled: bool) -> str:
    return '설정됨' if enabled else '없음'


def format_report(report: Report) -> str:
    lines = ['=== KS Bot 서버 상태 ===', '', '[호스트]']
    host = report.host
    lines.append(f'  호스트명 : {host.hostname}')
    lines.append(f'  업타임   : {format_duration(host.uptime_seconds) if host.uptime_seconds is not None else "(확인 불가)"}')
    if host.loadavg is not None:
        lines.append(f'  부하     : {host.loadavg[0]:.2f} {host.loadavg[1]:.2f} {host.loadavg[2]:.2f}')
    else:
        lines.append('  부하     : (확인 불가)')
    if host.mem_total is not None and host.mem_available is not None:
        used = host.mem_total - host.mem_available
        percent = used * 100 / host.mem_total if host.mem_total else 0
        lines.append(f'  메모리   : {format_bytes(used)} / {format_bytes(host.mem_total)} ({percent:.0f}%)')
    else:
        lines.append('  메모리   : (확인 불가)')
    if host.disk_total is not None and host.disk_used is not None:
        percent = host.disk_used * 100 / host.disk_total if host.disk_total else 0
        lines.append(f'  디스크   : {format_bytes(host.disk_used)} / {format_bytes(host.disk_total)} ({percent:.0f}%)')
    else:
        lines.append('  디스크   : (확인 불가)')

    lines.extend(['', '[프로세스]'])
    if report.process_error:
        lines.append(f'  상태     : 확인 불가 ({report.process_error})')
    elif report.processes:
        total = len(report.processes)
        for index, proc in enumerate(report.processes, start=1):
            if total > 1:
                lines.append(f'  --- 프로세스 {index}/{total} ---')
            lines.append('  상태     : 실행 중')
            lines.append(f'  PID      : {proc.pid}')
            lines.append(f'  경과     : {proc.etime}')
            lines.append(f'  메모리   : {format_bytes(proc.rss_kib * 1024)}')
            lines.append(f'  명령     : {redact_cmdline(proc.cmdline)}')
    else:
        lines.append('  상태     : 실행 중이지 않음')

    settings = report.settings
    lines.extend(['', '[설정]'])
    if report.config_error:
        lines.append(f'  오류     : {report.config_error}')
    lines.append(f'  .env     : {"있음" if settings.env_file else "없음"}')
    lines.append(f'  토큰     : {_flag(settings.discord_token)}')
    lines.append(f'  PUBG     : {_flag(settings.pubg)} → 밸런서 {"활성" if settings.pubg else "비활성"}')
    if settings.giveaway_channel_id:
        lines.append(f'  무료배포 : 채널 {settings.giveaway_channel_id}')
    else:
        lines.append('  무료배포 : 채널 없음 → 코그 비활성')
    if settings.slash_guild_id:
        lines.append(f'  슬래시   : 길드 {settings.slash_guild_id}')
    else:
        lines.append('  슬래시   : 전역 등록 (반영까지 최대 1시간)')
    lines.append(f'  접두사   : {settings.command_prefix}')
    lines.append(f'  로그     : {settings.log_level}')
    lines.append(f'  DB       : {settings.db_path} ({"있음" if settings.db_exists else "아직 없음"})')

    lines.extend(['', '[디스코드]'])
    if report.discord is None:
        lines.append('  상태     : 건너뜀 (--local 또는 토큰 없음)')
    elif not report.discord.ok:
        lines.append('  상태     : 실패')
        lines.append(f'  오류     : {report.discord.error}')
        if report.discord.user:
            lines.append(f'  봇       : {report.discord.user} ({report.discord.user_id})')
    else:
        discord = report.discord
        lines.append('  상태     : 연결됨 (REST)')
        lines.append(f'  봇       : {discord.user} ({discord.user_id})')
        if discord.latency_ms is not None:
            lines.append(f'  지연     : {discord.latency_ms:.0f} ms')
        lines.append(f'  서버 수  : {discord.guild_count}')
        if discord.giveaway_channel:
            lines.append(f'  무료배포 : {discord.giveaway_channel}')
        if discord.guild_filter_miss:
            lines.append(f'  (지정한 길드 {discord.guild_filter}를 찾지 못했습니다)')
        for guild in discord.guilds:
            lines.append(f'  ▸ {guild.name} ({guild.id})')
            members = f'{guild.member_count}' if guild.member_count is not None else '?'
            if guild.presence_count is not None:
                members += f' (온라인 {guild.presence_count})'
            lines.append(f'      멤버     : {members}')
            lines.append(f'      소유     : {"예" if guild.owner else "아니오"}')
        if not discord.guilds and not discord.guild_filter_miss:
            lines.append('  (봇이 속한 서버가 없습니다. README §3-1의 초대 링크로 추가하세요.)')
    return '\n'.join(lines)


def check_failed(report: Report) -> bool:
    if report.process_error or report.config_error or not report.processes:
        return True
    return report.discord is not None and not report.discord.ok


def _placeholder_settings() -> SettingsSummary:
    db_path = PROJECT_ROOT / 'res' / 'history.db'
    return SettingsSummary(
        env_file=(PROJECT_ROOT / '.env').is_file(),
        discord_token=False,
        pubg=False,
        giveaway_channel_id=0,
        slash_guild_id=0,
        command_prefix='?',
        log_level='?',
        db_path=db_path,
        db_exists=db_path.is_file(),
    )


async def build_report(args: argparse.Namespace) -> Report:
    host = collect_host()
    snapshot = collect_processes()

    try:
        settings = Settings.from_env(require_discord_token=False)
    except ConfigError as e:
        return Report(
            host=host,
            processes=snapshot.items,
            settings=_placeholder_settings(),
            discord=None if args.local else DiscordStatus(ok=False, error=e.message),
            process_error=snapshot.error,
            config_error=e.message,
        )

    token = args.token or settings.discord_token
    discord: DiscordStatus | None = None
    if not args.local:
        if not token:
            discord = DiscordStatus(ok=False, error='봇 토큰이 없습니다. --token 또는 DISCORD_TOKEN을 설정하세요.')
        else:
            discord = await collect_discord(
                token,
                giveaway_channel_id=settings.giveaway_channel_id,
                guild_id=args.guild_id,
            )
    return Report(
        host=host,
        processes=snapshot.items,
        settings=summarize_settings(settings, has_discord_token=bool(token)),
        discord=discord,
        process_error=snapshot.error,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging('WARNING')
    report = asyncio.run(build_report(args))
    print(format_report(report))
    if args.check and check_failed(report):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
