from conftest import PARAMETRIZE_INDICATOR
import pytest
from ks_bot.core.pubg_balancer import *
from ks_bot.common.error import *
from testdata import *


# @pytest.mark.asyncio
# @pytest.mark.parametrize(
#     PARAMETRIZE_INDICATOR,
#     [
#         ('SonPANG', TestData_Player.REAL_PLAYER1),
#         ('SonPANg', PlayerNotFoundError_Balancer),
#     ],
# )
# async def test_get_player(pubg_balancer: PUBG_Balancer, input: str, expected: Player):
#     print(input)
#     player = await pubg_balancer.get_player(player_name=input)
#     print(f'player: {player}')
#     if isinstance(player, Player):
#         print('a')
#         assert player.id == expected.id and player.name == expected.name and player.platform == expected.platform
#     else:
#         print('b')
#         assert isinstance(player, expected)
