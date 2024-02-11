import pytest

from ks_bot.core.db_handler import SQLiteDBHandler
from ks_bot.core.request_handler import APIRequestHandler, HttpMethod
from ks_bot.core.pubg_balancer import PUBG_Balancer
from ks_bot.utils import *

TEST_DB = 'test_history.db'
PARAMETRIZE_INDICATOR = 'input, expected'


@pytest.fixture
async def db_handler():
    handler = SQLiteDBHandler(TEST_DB)
    await handler.init()
    yield handler
    await handler.close()


@pytest.fixture
async def api_request_handler():
    api_key = get_pubg_token()
    platform = 'steam'
    base_url = f'https://api.pubg.com/shards/{platform}'
    api_request_handler = APIRequestHandler(api_key=api_key, base_url=base_url)
    return api_request_handler


@pytest.fixture
async def pubg_balancer():
    api_key = get_pubg_token()
    platform = 'steam'
    async with PUBG_Balancer(api_key=api_key, platform=platform, db_init=True) as pubg_balancer:
        yield pubg_balancer


def validate_dict_structure(schema: dict, target_dict: dict) -> bool:
    for key, value_type in schema.items():
        if key not in target_dict:
            return False

        actual_value = target_dict[key]
        if isinstance(value_type, dict):
            if not isinstance(actual_value, dict) or not validate_dict_structure(value_type, actual_value):
                return False
        else:
            if not isinstance(actual_value, value_type):
                return False
    return True
