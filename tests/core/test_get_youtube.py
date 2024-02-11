import pytest
from ks_bot.core.get_youtube import *
from conftest import PARAMETRIZE_INDICATOR


@pytest.mark.asyncio
@pytest.mark.parametrize(
    PARAMETRIZE_INDICATOR,
    [
        ("https://www.youtube.com/watch?v=SK6Sm2Ki9tI", True),
        ("https://youtu.be/SK6Sm2Ki9tI", True),
        ("http://www.example.com", True),
        ("not_a_url", False),
    ],
)
async def test_is_valid_url(input, expected):
    assert await is_valid_url(input) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    PARAMETRIZE_INDICATOR,
    [
        ("이무진 신호등", "youtube.com"),
        ("Python asyncio tutorial", "youtube.com"),
    ],
)
async def test_search_youtube(input, expected):
    result_url = await search_youtube(input)
    assert expected in result_url


@pytest.mark.asyncio
@pytest.mark.parametrize(
    PARAMETRIZE_INDICATOR,
    [
        ("https://www.youtube.com/watch?v=SK6Sm2Ki9tI", "이무진"),
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Rick Astley"),
    ],
)
async def test_get_youtube_with_url(input, expected):
    info = await get_youtube(input)
    assert expected in info["title"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    PARAMETRIZE_INDICATOR,
    [
        ("이무진 신호등", "신호등"),
        ("Rick Astley Never Gonna Give You Up", "Rick Astley"),
    ],
)
async def test_get_youtube_with_query(input, expected):
    info = await get_youtube(input)
    assert expected in info["title"]
