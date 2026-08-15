"""로깅 설정.

`print` 대신 표준 `logging`을 사용해 레벨/출처를 함께 남긴다.
터미널에서는 레벨별 색상을 입힌다.
"""

from __future__ import annotations

import logging
import sys

from termcolor import colored

__all__ = ['get_logger', 'setup_logging']

_LEVEL_COLORS = {
    logging.DEBUG: 'cyan',
    logging.INFO: 'green',
    logging.WARNING: 'yellow',
    logging.ERROR: 'red',
    logging.CRITICAL: 'magenta',
}


class ColoredFormatter(logging.Formatter):
    """레벨 이름에만 색을 입히는 포매터."""

    def format(self, record: logging.LogRecord) -> str:
        original_levelname = record.levelname
        color = _LEVEL_COLORS.get(record.levelno)
        if color and sys.stderr.isatty():
            record.levelname = colored(original_levelname, color)
        try:
            return super().format(record)
        finally:
            record.levelname = original_levelname


def setup_logging(level: str = 'INFO') -> None:
    """루트 로거를 1회 구성한다. 중복 호출해도 핸들러가 늘어나지 않는다."""
    root = logging.getLogger()
    root.setLevel(level.upper())

    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(ColoredFormatter(fmt='%(asctime)s %(levelname)s [%(name)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    root.addHandler(handler)

    # discord.py 내부 로그는 너무 자세하므로 한 단계 낮춘다.
    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('discord.http').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
