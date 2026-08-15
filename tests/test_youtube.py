"""유튜브 조회 모듈 테스트(네트워크 없이 동작)."""

from __future__ import annotations

import pytest

from ks_bot.core import youtube
from ks_bot.core.youtube import TrackInfo, get_youtube, is_valid_url

_YDL_INFO = {
    'webpage_url': 'https://www.youtube.com/watch?v=abc',
    'title': '신호등',
    'uploader': '이무진',
    'channel_url': 'https://www.youtube.com/@leemujin',
    'url': 'https://stream.example.com/audio.m4a',
    'thumbnail': 'https://img.example.com/thumb.jpg',
}


class TestUrlValidation:
    @pytest.mark.parametrize(
        'value, expected',
        [
            ('https://www.youtube.com/watch?v=SK6Sm2Ki9tI', True),
            ('https://youtu.be/SK6Sm2Ki9tI', True),
            ('http://www.example.com', True),
            ('not_a_url', False),
            ('', False),
        ],
    )
    async def test_is_valid_url(self, value: str, expected: bool):
        assert await is_valid_url(value) is expected


class TestTrackInfo:
    def test_from_ydl_maps_fields(self):
        info = TrackInfo.from_ydl(_YDL_INFO)
        assert info.title == '신호등'
        assert info.uploader_url.endswith('leemujin')
        assert info.target_url.endswith('audio.m4a')
        assert info.is_playable is True

    def test_empty_info_is_not_playable(self):
        assert TrackInfo.from_ydl({}).is_playable is False


class TestGetYoutube:
    async def test_url_input_skips_search(self, monkeypatch):
        monkeypatch.setattr(youtube, '_extract_info', lambda url: _YDL_INFO)
        monkeypatch.setattr(youtube, '_search_first_video_url', lambda *a: pytest.fail('URL 입력에는 검색을 하면 안 된다.'))

        info = await get_youtube('https://www.youtube.com/watch?v=abc')
        assert info.title == '신호등'

    async def test_query_input_searches_first(self, monkeypatch):
        monkeypatch.setattr(youtube, '_search_first_video_url', lambda query, limit: 'https://www.youtube.com/watch?v=abc')
        monkeypatch.setattr(youtube, '_extract_info', lambda url: _YDL_INFO)

        info = await get_youtube('이무진 신호등')
        assert info.title == '신호등'

    async def test_search_failure_returns_empty_track(self, monkeypatch):
        monkeypatch.setattr(youtube, '_search_first_video_url', lambda query, limit: '')

        info = await get_youtube('없는노래')
        assert info.is_playable is False

    async def test_extract_failure_returns_empty_track(self, monkeypatch):
        def boom(url: str):
            raise RuntimeError('yt-dlp 실패')

        monkeypatch.setattr(youtube, '_extract_info', boom)

        info = await get_youtube('https://www.youtube.com/watch?v=abc')
        assert info.is_playable is False

    async def test_search_exception_is_swallowed(self, monkeypatch):
        def boom(query: str, limit: int):
            raise RuntimeError('검색 실패')

        monkeypatch.setattr(youtube, '_search_first_video_url', boom)

        assert await youtube.search_youtube('쿼리') == ''
