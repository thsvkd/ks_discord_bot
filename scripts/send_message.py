"""봇 토큰/채널 ID 점검용 스크립트.

지정한 채널에 메시지를 한 번 보내고 즉시 종료한다.

사용법:
    python scripts/send_message.py --channel-id 1234567890123456789 --message "테스트 ✅"

토큰은 `--token` 인자 → `DISCORD_TOKEN` 환경 변수 → `.env` 순으로 찾는다.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import discord

# 저장소 어디에서 실행해도 `ks_bot` 패키지를 찾을 수 있게 한다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ks_bot.config import Settings
from ks_bot.logging_config import get_logger, setup_logging

logger = get_logger('send_message')


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='디스코드 채널에 메시지를 한 번 전송합니다.')
    parser.add_argument('--channel-id', type=int, required=True, help='대상 채널 ID (디스코드 개발자 모드 → 채널 우클릭 → 채널 ID 복사)')
    parser.add_argument('--message', default='KS Bot 연결 테스트 ✅', help='보낼 메시지 내용')
    parser.add_argument('--token', default=None, help='봇 토큰 (생략 시 DISCORD_TOKEN 환경 변수 또는 .env 사용)')
    return parser.parse_args(argv)


async def send_message(token: str, channel_id: int, content: str) -> int:
    """메시지를 전송하고 메시지 ID를 반환한다."""
    client = discord.Client(intents=discord.Intents.none())
    outcome: dict[str, object] = {}

    @client.event
    async def on_ready() -> None:
        if 'done' in outcome:  # 재연결 시 중복 전송 방지
            return
        outcome['done'] = True
        try:
            channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
            sent = await channel.send(content)
            outcome['message_id'] = sent.id
            logger.info('메시지를 전송했습니다. channel=%s, message_id=%s', channel_id, sent.id)
        except discord.NotFound:
            outcome['error'] = f'채널을 찾을 수 없습니다: {channel_id}. 채널 ID가 맞는지, 봇이 해당 서버에 있는지 확인하세요.'
        except discord.Forbidden:
            outcome['error'] = f'봇이 채널 {channel_id}에 메시지를 보낼 권한이 없습니다. 채널 권한(채널 보기/메시지 보내기)을 확인하세요.'
        except discord.HTTPException as e:
            outcome['error'] = f'메시지 전송에 실패했습니다: {e}'
        finally:
            await client.close()

    try:
        await client.start(token)
    except discord.LoginFailure as e:
        raise SystemExit(f'봇 토큰이 올바르지 않습니다: {e}') from e

    if 'error' in outcome:
        raise SystemExit(str(outcome['error']))
    if 'message_id' not in outcome:
        raise SystemExit('메시지를 전송하지 못했습니다.')
    return int(outcome['message_id'])


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging('INFO')

    token = args.token or Settings.from_env(require_discord_token=False).discord_token
    if not token:
        logger.error('봇 토큰이 없습니다. --token 인자를 주거나 DISCORD_TOKEN 환경 변수를 설정하세요.')
        return 1

    message_id = asyncio.run(send_message(token, args.channel_id, args.message))
    print(f'전송 완료: channel_id={args.channel_id}, message_id={message_id}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
