"""봇 실행 엔트리포인트: `python -m ks_bot`."""

from __future__ import annotations

import asyncio
import sys

from ks_bot.bot import KSBot
from ks_bot.common.errors import ConfigError
from ks_bot.config import Settings
from ks_bot.logging_config import get_logger, setup_logging

logger = get_logger(__name__)


async def run_bot(settings: Settings) -> None:
    bot = KSBot(settings)
    async with bot:
        await bot.start(settings.discord_token)


def main() -> int:
    try:
        settings = Settings.from_env()
    except ConfigError as e:
        setup_logging('INFO')
        logger.error('%s', e.message)
        return 1

    setup_logging(settings.log_level)

    try:
        asyncio.run(run_bot(settings))
    except KeyboardInterrupt:
        logger.info('사용자 요청으로 봇을 종료합니다.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
