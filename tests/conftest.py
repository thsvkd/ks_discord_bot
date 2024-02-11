import pytest
import os

from ks_bot.core.db_handler import SQLiteDBHandler
from ks_bot.core.request_handler import APIRequestHandler, HttpMethod

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
    api_key = os.environ.get('PUBG_TOKEN')
    platform = 'steam'
    base_url = f'https://api.pubg.com/shards/{platform}'
    api_request_handler = APIRequestHandler(api_key=api_key, base_url=base_url)
    return api_request_handler
