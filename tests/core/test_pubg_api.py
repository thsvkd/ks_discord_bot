from conftest import PARAMETRIZE_INDICATOR
import pytest
from ks_bot.core.pubg_api import *


@pytest.mark.asyncio
async def test_api_request_handler_get_request(api_request_handler: APIRequestHandler):
    headers = {"Authorization": f"Bearer {api_request_handler.api_key}", "Accept": "application/vnd.api+json"}
    response = await api_request_handler.request(endpoint='seasons', method=HttpMethod.GET, headers=headers)

    assert not isinstance(response, ErrorCode_Balancer)
