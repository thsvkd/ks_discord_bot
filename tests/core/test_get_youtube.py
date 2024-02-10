import pytest
from ks_bot.core.get_youtube import is_valid_url, search_youtube, get_youtube


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.youtube.com/watch?v=SK6Sm2Ki9tI", True),
        ("https://youtu.be/SK6Sm2Ki9tI", True),
        ("http://www.example.com", True),
        ("not_a_url", False),
    ],
)
async def test_is_valid_url(url, expected):
    assert await is_valid_url(url) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query,expected_substring",
    [
        ("이무진 신호등", "youtube.com"),
        ("Python asyncio tutorial", "youtube.com"),
    ],
)
async def test_search_youtube(query, expected_substring):
    result_url = await search_youtube(query)
    assert expected_substring in result_url


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url,expected_title_substring",
    [
        ("https://www.youtube.com/watch?v=SK6Sm2Ki9tI", "이무진"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Rick Astley"),
    ],
)
async def test_get_youtube_with_url(url, expected_title_substring):
    info = await get_youtube(url)
    assert expected_title_substring in info["title"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query,expected_title_substring",
    [
        ("이무진 신호등", "신호등"),
        ("Rick Astley Never Gonna Give You Up", "Rick Astley"),
    ],
)
async def test_get_youtube_with_query(query, expected_title_substring):
    info = await get_youtube(query)
    assert expected_title_substring in info["title"]
