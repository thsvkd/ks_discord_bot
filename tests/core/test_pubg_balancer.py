from conftest import PARAMETRIZE_INDICATOR, validate_dict_structure
import pytest
from ks_bot.core.pubg_balancer import *
from ks_bot.common.error import *
from testdata import *


@pytest.mark.asyncio
@pytest.mark.parametrize(
    PARAMETRIZE_INDICATOR,
    [
        ('SonPANG', TestData_Player.REAL_PLAYER1),
        ('SonPANg', PlayerNotFoundError_Balancer),
    ],
)
async def test_request_player(pubg_balancer: PUBG_Balancer, input: str, expected: Player):
    player = await pubg_balancer._request_player(player_name=input)
    if isinstance(player, Player):
        assert player.id == expected.id and player.name == expected.name and player.platform == expected.platform
    else:
        assert isinstance(player, expected)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    PARAMETRIZE_INDICATOR,
    [
        (None, {'type': str, 'id': str, 'attributes': {'isCurrentSeason': bool, 'isOffseason': bool}}),
    ],
)
async def test_request_seasons_data(pubg_balancer: PUBG_Balancer, input: str, expected: Player):
    seasons_data = await pubg_balancer._request_seasons_data()
    assert validate_dict_structure(schema=expected, target_dict=seasons_data)


# @pytest.mark.asyncio
# async def test_request_rank_stats(pubg_balancer: PUBG_Balancer, input: str, expected: Player):
#     pass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    PARAMETRIZE_INDICATOR,
    [
        (
            'clan.fab1814f906d49b08d77b3adb783cc24',
            {
                'data': {
                    'type': str,
                    'id': str,
                    'attributes': {'clanName': str, 'clanTag': str, 'clanLevel': int, 'clanMemberCount': int},
                },
                'links': {'self': str},
                'meta': {},
            },
        ),
    ],
)
async def test_request_clan_data(pubg_balancer: PUBG_Balancer, input: str, expected: Player):
    clan_data = await pubg_balancer._request_clan_data(clan_id=input)
    assert validate_dict_structure(schema=expected, target_dict=clan_data)


if __name__ == '__main__':
    pytest.main(['-sx', '-v', __file__])
