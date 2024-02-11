from typing import List, Tuple
import pytest
import asyncio
from conftest import PARAMETRIZE_INDICATOR
from testdata import *


from ks_bot.core.db_handler import *


@pytest.mark.asyncio
@pytest.mark.parametrize(  # normalized_id: str, player_name: str
    PARAMETRIZE_INDICATOR,
    [
        (TestData_Player.EXAMPLE_PLAYER1_1, TestData_Player.EXAMPLE_PLAYER1_1),
        (TestData_Player.EXAMPLE_PLAYER1_2, TestData_Player.EXAMPLE_PLAYER1_2),
        (TestData_Player.EXAMPLE_PLAYER1_3, TestData_Player.EXAMPLE_PLAYER1_3),
        (TestData_Player.EXAMPLE_PLAYER1_4, TestData_Player.EXAMPLE_PLAYER1_4),
    ],
)
async def test_insert_fetch_player(db_handler: SQLiteDBHandler, input: Player, expected: Player):
    await db_handler.insert_player(input)
    result = await db_handler.get_player(input.normalized_id)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(  # normalized_id: str, player_name: str
    PARAMETRIZE_INDICATOR,
    [
        (
            (
                TestData_Player.EXAMPLE_PLAYER1_4,
                TestData_Player.EXAMPLE_PLAYER2,
                TestData_Player.EXAMPLE_PLAYER3,
            ),
            (TestData_Player.EXAMPLE_PLAYER1_4, True),
        ),
        (
            (
                TestData_Player.EXAMPLE_PLAYER1_4,
                TestData_Player.EXAMPLE_PLAYER2,
                TestData_Player.EXAMPLE_PLAYER3,
            ),
            (TestData_Player.EXAMPLE_PLAYER2, True),
        ),
        (
            (
                TestData_Player.EXAMPLE_PLAYER1_4,
                TestData_Player.EXAMPLE_PLAYER2,
                TestData_Player.EXAMPLE_PLAYER3,
            ),
            (TestData_Player.EXAMPLE_PLAYER3, True),
        ),
        (
            (
                TestData_Player.EXAMPLE_PLAYER1_4,
                TestData_Player.EXAMPLE_PLAYER2,
                TestData_Player.EXAMPLE_PLAYER3,
            ),
            (TestData_Player.EXAMPLE_PLAYER4, False),
        ),
        (
            (),
            (TestData_Player.EXAMPLE_PLAYER1_4, False),
        ),
    ],
)
async def test_is_player_exists(db_handler: SQLiteDBHandler, input: Tuple[Player], expected: Tuple[Player, bool]):
    for player in input:
        await db_handler.insert_player(player)

    result = await db_handler.is_player_exists(expected[0].normalized_id)
    assert result == expected[1]


@pytest.mark.asyncio
@pytest.mark.parametrize(  # normalized_id: str, player_name: str
    PARAMETRIZE_INDICATOR,
    [
        (
            TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS1,
            TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS1,
        ),
        (
            TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS2,
            TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS2,
        ),
        (
            TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS3,
            TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS3,
        ),
        (
            TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS4,
            TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS4,
        ),
    ],
)
async def test_insert_fetch_player_match_stats(db_handler: SQLiteDBHandler, input: Tuple[Player, PlayerMatchStats], expected: PlayerMatchStats):
    await db_handler.insert_player(input[0])
    await db_handler.insert_player_match_stats(input[1])
    result = await db_handler.get_player_match_stats(input[0].name, input[1].match_id)
    assert result == expected[1]


@pytest.mark.asyncio
@pytest.mark.parametrize(  # normalized_id: str, player_name: str
    PARAMETRIZE_INDICATOR,
    [
        (
            (
                TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS1,
                TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS2,
                TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS3,
            ),
            (TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS1, True),
        ),
        (
            (
                TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS1,
                TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS2,
                TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS3,
            ),
            (TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS2, True),
        ),
        (
            (
                TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS1,
                TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS2,
                TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS3,
            ),
            (TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS3, True),
        ),
        (
            (
                TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS1,
                TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS2,
                TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS3,
            ),
            (TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS4, False),
        ),
        (
            (),
            (TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS1, False),
        ),
    ],
)
async def test_is_player_match_stats_exists(
    db_handler: SQLiteDBHandler, input: Tuple[Tuple[Player, PlayerMatchStats]], expected: Tuple[Tuple[Player, PlayerMatchStats], bool]
):
    for player, player_match_stats in input:
        print(player, player_match_stats)
        if not await db_handler.is_player_exists(player.normalized_id):
            await db_handler.insert_player(player)

        await db_handler.insert_player_match_stats(player_match_stats)

    result = await db_handler.is_player_match_stats_exists(expected[0][0].name, expected[0][1].match_id)
    assert result == expected[1]


@pytest.mark.asyncio
@pytest.mark.parametrize(  # normalized_id: str, player_name: str
    PARAMETRIZE_INDICATOR,
    [
        (
            (
                TestData_Player.EXAMPLE_PLAYER1_4,
                timedelta(seconds=2),
                timedelta(seconds=1),
            ),
            False,
        ),
        (
            (
                TestData_Player.EXAMPLE_PLAYER1_4,
                timedelta(seconds=2),
                timedelta(seconds=3),
            ),
            True,
        ),
    ],
)
async def test_is_player_data_outdated(db_handler: SQLiteDBHandler, input: Tuple[Player, datetime, timedelta], expected: bool):
    await db_handler.insert_player(input[0])
    await asyncio.sleep(input[2].total_seconds())

    result = await db_handler.is_player_data_outdated(normalized_id=input[0].normalized_id, expiration_period=input[1])
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(  # normalized_id: str, player_name: str
    PARAMETRIZE_INDICATOR,
    [
        (
            (
                TestData_Player.EXAMPLE_PLAYER1_4,
                TestData_Player.EXAMPLE_PLAYER1_3,
            ),
            TestData_Player.EXAMPLE_PLAYER1_3,
        ),
    ],
)
async def test_update_player(db_handler: SQLiteDBHandler, input: Tuple[Player, Player], expected: Player):
    await db_handler.insert_player(input[0])
    await db_handler.update_player(input[1])
    result = await db_handler.get_player(input[0].normalized_id)
    assert result == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(  # normalized_id: str, player_name: str
    PARAMETRIZE_INDICATOR,
    [
        (
            (
                TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS1,
                TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS5,
            ),
            TestData_PlayerMatchStats.EXAMPLE_PLAYER_MATCH_STATS5,
        ),
    ],
)
async def test_update_player_match_stats(
    db_handler: SQLiteDBHandler, input: Tuple[Tuple[Player, PlayerMatchStats]], expected: Tuple[Player, PlayerMatchStats]
):
    await db_handler.insert_player(input[0][0])
    await db_handler.insert_player_match_stats(input[0][1])
    await db_handler.update_player_match_stats(input[1][1])
    result = await db_handler.get_player_match_stats(input[0][0].name, input[0][1].match_id)
    assert result == expected[1]
