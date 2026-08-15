"""무료 배포 알림 미리보기 스크립트.

봇을 상시 띄우지 않고도, 지금 수집되는 배포와 실제 발행 형태를 확인할 수 있다.
알림 채널을 정하기 전에 결과를 눈으로 확인하는 용도다.

사용법:
    # 수집 결과만 터미널에 출력 (디스코드 전송 없음)
    python scripts/preview_giveaways.py --dry-run

    # 지정한 채널에 실제로 발행해보기
    python scripts/preview_giveaways.py --channel-id 1234567890123456789

기본적으로 임시 DB를 쓰므로 실제 봇의 발행 이력에는 영향을 주지 않는다.
(`--persist`를 주면 설정된 DB를 그대로 사용한다.)
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import discord

# 저장소 어디에서 실행해도 `ks_bot` 패키지와 옆 스크립트를 찾을 수 있게 한다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from send_message import _run_client

from ks_bot.cogs.giveaway import GiveawayCog
from ks_bot.common.giveaway import ClaimKind, Giveaway
from ks_bot.config import Settings
from ks_bot.logging_config import get_logger, setup_logging

logger = get_logger('preview_giveaways')


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='무료 배포 수집 결과를 확인하고, 선택적으로 채널에 발행합니다.')
    parser.add_argument('--channel-id', type=int, help='발행할 채널 ID (생략 시 KS_BOT_GIVEAWAY_CHANNEL_ID)')
    parser.add_argument('--dry-run', action='store_true', help='디스코드에 보내지 않고 수집 결과만 출력합니다.')
    parser.add_argument('--persist', action='store_true', help='임시 DB 대신 설정된 DB를 사용합니다(발행 이력이 남습니다).')
    parser.add_argument('--token', default=None, help='봇 토큰 (생략 시 DISCORD_TOKEN 환경 변수 또는 .env 사용)')
    return parser.parse_args(argv)


def describe(giveaway: Giveaway) -> str:
    lines = [
        f'▸ {giveaway.title} [{giveaway.store.label}]{" (예정)" if giveaway.is_upcoming else ""}',
        f'    링크   : {giveaway.url}',
        f'    가격   : {giveaway.original_price or "(없음)"} → 무료',
        f'    장르   : {" · ".join(giveaway.genres) or "(없음)"}',
        f'    마감   : {giveaway.ends_at or "미정"}',
        f'    방식   : {"선착순 키" if giveaway.claim_kind is ClaimKind.KEY_DROP else "스토어 무료"} (출처 {giveaway.source})',
    ]
    if giveaway.description:
        lines.append(f'    설명   : {giveaway.description[:100]}')
    return '\n'.join(lines)


async def collect(settings: Settings) -> tuple[GiveawayCog, list[Giveaway]]:
    """코그를 그대로 만들어 수집한다(실제 발행 경로와 같은 코드를 쓴다)."""
    cog = GiveawayCog(SimpleNamespace(settings=settings))
    await cog.service.connect()
    return cog, await cog.service.find_new()


async def preview(settings: Settings, *, token: str, channel_id: int | None, dry_run: bool) -> int:
    cog, giveaways = await collect(settings)
    try:
        print(f'=== 수집된 무료 배포: {len(giveaways)}건 ===')
        for giveaway in giveaways:
            print(describe(giveaway))

        if dry_run or not giveaways:
            return len(giveaways)

        async def action(client: discord.Client, outcome: dict[str, object]) -> None:
            channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
            outcome['announced'] = await cog.announce(channel, giveaways)

        outcome = await _run_client(token, action)
        return int(outcome.get('announced', 0))
    finally:
        await cog.service.aclose()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging('INFO')

    settings = Settings.from_env(require_discord_token=False)
    token = args.token or settings.discord_token
    channel_id = args.channel_id or settings.giveaway_channel_id

    if not args.dry_run:
        if not token:
            logger.error('봇 토큰이 없습니다. --token 인자를 주거나 DISCORD_TOKEN 환경 변수를 설정하세요.')
            return 1
        if not channel_id:
            logger.error('채널 ID가 없습니다. --channel-id 인자를 주거나 KS_BOT_GIVEAWAY_CHANNEL_ID를 설정하세요.')
            return 1

    with tempfile.TemporaryDirectory() as tmp_dir:
        if not args.persist:
            settings = replace(settings, db_path=Path(tmp_dir) / 'preview.db')
        announced = asyncio.run(preview(settings, token=token, channel_id=channel_id, dry_run=args.dry_run))

    if not args.dry_run:
        print(f'발행 완료: {announced}건 (channel_id={channel_id})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
