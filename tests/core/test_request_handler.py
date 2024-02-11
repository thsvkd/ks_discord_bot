from conftest import PARAMETRIZE_INDICATOR
import pytest
from ks_bot.core.request_handler import *
from ks_bot.common.error import *


@pytest.mark.asyncio
async def test_api_request_handler_get_request(api_request_handler: APIRequestHandler):
    headers = {"Authorization": f"Bearer {api_request_handler.api_key}", "Accept": "application/vnd.api+json"}
    response = await api_request_handler.request(endpoint='seasons', method=HttpMethod.GET, header=headers)

    assert not isinstance(response, ErrorCode_Balancer)


if __name__ == '__main__':
    pytest.main(['-sx', '-v', __file__])
