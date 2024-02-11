import pytest

from ks_bot.core.db_handler import SQLiteDBHandler

# 테스트를 위한 임시 데이터베이스 파일 경로
TEST_DB = 'test_history.db'
PARAMETRIZE_INDICATOR = 'input, expected'


@pytest.fixture
async def db_handler():
    handler = SQLiteDBHandler(TEST_DB)
    await handler.init()
    yield handler
    await handler.close()
