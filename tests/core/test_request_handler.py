from conftest import PARAMETRIZE_INDICATOR, validate_dict_structure, async_exception_test
import pytest
from typing import List, Dict, Union
from ks_bot.core.request_handler import *
from ks_bot.common.error import *


@pytest.mark.asyncio
@pytest.mark.parametrize(
    PARAMETRIZE_INDICATOR,
    [
        (
            'seasons',
            {'data': [{'type': str, 'id': str, 'attributes': {'isCurrentSeason': bool, 'isOffseason': bool}}], 'links': {'self': str}, 'meta': dict},
        ),
    ],
)
@async_exception_test()
async def test_api_request_handler_get_request(api_request_handler: APIRequestHandler, input: str, expected: dict):
    headers = {"Authorization": f"Bearer {api_request_handler.api_key}", "Accept": "application/vnd.api+json"}
    result = await api_request_handler.request(endpoint=input, method=HttpMethod.GET, header=headers)
    assert validate_dict_structure(schema=expected, target_dict=result)


if __name__ == '__main__':
    pytest.main(['-sx', '-v', __file__])
