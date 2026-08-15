"""유튜브 검색/메타데이터 조회.

`yt_dlp`는 동기 라이브러리이므로 별도 스레드에서 실행해 이벤트 루프를 막지 않는다.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from urllib.parse import urlparse

from youtubesearchpython import VideosSearch
from yt_dlp import YoutubeDL

from ks_bot.logging_config import get_logger

__all__ = ['FFMPEG_BEFORE_ARGS', 'TrackInfo', 'get_youtube', 'get_youtube_info', 'is_valid_url', 'search_youtube']

logger = get_logger(__name__)

# 스트리밍 URL이 끊겼을 때 FFmpeg가 재접속하도록 하는 옵션.
FFMPEG_BEFORE_ARGS = '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'

_YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'noplaylist': True,
}


@dataclass(frozen=True)
class TrackInfo:
    """재생 대상 트랙 정보."""

    webpage_url: str = ''
    title: str = ''
    uploader: str = ''
    uploader_url: str = ''
    target_url: str = ''
    thumbnail: str = ''

    @property
    def is_playable(self) -> bool:
        return bool(self.target_url)

    @classmethod
    def from_ydl(cls, info: dict) -> TrackInfo:
        return cls(
            webpage_url=info.get('webpage_url', ''),
            title=info.get('title', ''),
            uploader=info.get('uploader', ''),
            uploader_url=info.get('channel_url', ''),
            target_url=info.get('url', ''),
            thumbnail=info.get('thumbnail', ''),
        )


async def is_valid_url(input_string: str) -> bool:
    """스킴과 호스트가 모두 있는 URL인지 판단한다."""
    try:
        result = urlparse(input_string)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def _extract_info(url: str) -> dict:
    with YoutubeDL(_YDL_OPTIONS) as ydl:
        return ydl.extract_info(url, download=False) or {}


async def get_youtube_info(url: str) -> TrackInfo:
    """URL의 스트리밍 정보를 조회한다."""
    info = await asyncio.to_thread(_extract_info, url)
    return TrackInfo.from_ydl(info)


def _search_first_video_url(query: str, max_results: int) -> str:
    results = VideosSearch(query, limit=max_results).result().get('result', [])
    return results[0]['link'] if results else ''


async def search_youtube(query: str, max_results: int = 1) -> str:
    """검색어로 첫 번째 영상 URL을 찾는다. 실패하면 빈 문자열."""
    try:
        return await asyncio.to_thread(_search_first_video_url, query, max_results)
    except Exception:  # 검색 라이브러리는 다양한 예외를 던진다.
        logger.exception('유튜브 검색에 실패했습니다. query=%s', query)
        return ''


async def get_youtube(url_or_query: str) -> TrackInfo:
    """URL이면 바로, 검색어면 검색 후 트랙 정보를 반환한다."""
    url = url_or_query if await is_valid_url(url_or_query) else await search_youtube(url_or_query)
    if not url:
        logger.warning('재생할 수 있는 URL을 찾지 못했습니다. input=%s', url_or_query)
        return TrackInfo()

    try:
        return await get_youtube_info(url)
    except Exception:
        logger.exception('유튜브 정보를 가져오지 못했습니다. url=%s', url)
        return TrackInfo()
