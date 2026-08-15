"""HTTP 클라이언트 테스트. 로컬 테스트 서버를 띄워 네트워크 없이 검증한다."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from ks_bot.common.errors import ApiRequestError, RateLimitError, ResourceNotFoundError
from ks_bot.core.http_client import ApiClient, HttpMethod


@asynccontextmanager
async def make_client(handler: Callable[[web.Request], web.StreamResponse]) -> AsyncIterator[ApiClient]:
    """핸들러 하나짜리 로컬 서버에 연결된 클라이언트를 제공한다."""
    app = web.Application()
    app.router.add_route('*', '/{tail:.*}', handler)
    server = TestServer(app)
    await server.start_server()

    client = ApiClient(api_key='test-key', base_url=str(server.make_url('')).rstrip('/'), max_retries=1, timeout=5.0)
    try:
        yield client
    finally:
        await client.aclose()
        await server.close()


class TestSuccess:
    async def test_returns_json_and_updates_rate_limit(self):
        async def handler(request: web.Request) -> web.Response:
            return web.json_response({'ok': True}, headers={'X-RateLimit-Remaining': '7', 'X-RateLimit-Reset': '12345'})

        async with make_client(handler) as client:
            assert await client.request('seasons') == {'ok': True}
            assert client.remaining_requests == 7
            assert client.rate_limit_reset_timestamp == 12345.0

    async def test_default_headers_include_bearer_token(self):
        captured: dict[str, str] = {}

        async def handler(request: web.Request) -> web.Response:
            captured.update(request.headers)
            return web.json_response({})

        async with make_client(handler) as client:
            await client.request('seasons', method=HttpMethod.GET)

        assert captured['Authorization'] == 'Bearer test-key'
        assert captured['Accept'] == 'application/vnd.api+json'

    async def test_session_is_reused_between_requests(self):
        async def handler(request: web.Request) -> web.Response:
            return web.json_response({})

        async with make_client(handler) as client:
            await client.request('a')
            first_session = client._session
            await client.request('b')
            assert client._session is first_session


class TestErrorMapping:
    async def test_404_raises_resource_not_found(self):
        async def handler(request: web.Request) -> web.Response:
            return web.json_response({'errors': []}, status=404)

        async with make_client(handler) as client:
            with pytest.raises(ResourceNotFoundError):
                await client.request('players/unknown')

    async def test_500_raises_api_request_error(self):
        async def handler(request: web.Request) -> web.Response:
            return web.json_response({}, status=500)

        async with make_client(handler) as client:
            with pytest.raises(ApiRequestError):
                await client.request('seasons')


class TestRateLimit:
    async def test_retries_after_429(self):
        state = {'calls': 0}

        async def handler(request: web.Request) -> web.Response:
            state['calls'] += 1
            if state['calls'] == 1:
                return web.json_response({}, status=429, headers={'X-RateLimit-Reset': str(time.time() - 10)})
            return web.json_response({'ok': True})

        async with make_client(handler) as client:
            assert await client.request('seasons') == {'ok': True}
            assert state['calls'] == 2

    async def test_gives_up_after_repeated_429(self):
        async def handler(request: web.Request) -> web.Response:
            return web.json_response({}, status=429, headers={'X-RateLimit-Reset': str(time.time() - 10)})

        async with make_client(handler) as client:
            with pytest.raises(RateLimitError):
                await client.request('seasons')


class TestAbsoluteUrlAndHeaders:
    async def test_absolute_endpoint_bypasses_base_url(self):
        async def handler(request: web.Request) -> web.Response:
            return web.json_response({'path': request.path})

        async with make_client(handler) as client:
            absolute = f'{client.base_url}/somewhere'
            assert await client.request(absolute) == {'path': '/somewhere'}

    async def test_custom_default_headers_replace_bearer(self):
        captured: dict[str, str] = {}

        async def handler(request: web.Request) -> web.Response:
            captured.update(request.headers)
            return web.json_response({})

        async with make_client(handler) as client:
            client._default_headers = {'User-Agent': 'test-agent'}
            await client.request('public')

        assert captured['User-Agent'] == 'test-agent'
        assert 'Authorization' not in captured


class TestResolveFinalUrl:
    async def test_follows_redirect(self):
        async def handler(request: web.Request) -> web.StreamResponse:
            if request.path == '/open':
                raise web.HTTPFound('/store/app/214340')
            return web.json_response({})

        async with make_client(handler) as client:
            assert (await client.resolve_final_url('open')).endswith('/store/app/214340')

    async def test_destination_error_status_still_yields_the_url(self):
        """스토어가 봇으로 의심해 403을 줘도, 주소 자체는 상품 식별에 쓸 수 있다."""

        async def handler(request: web.Request) -> web.StreamResponse:
            if request.path == '/open':
                raise web.HTTPFound('/p/caravan-sandwitch')
            return web.json_response({'error': 'forbidden'}, status=403)

        async with make_client(handler) as client:
            assert (await client.resolve_final_url('open')).endswith('/p/caravan-sandwitch')

    async def test_without_redirect_returns_the_same_url(self):
        async def handler(request: web.Request) -> web.Response:
            return web.json_response({})

        async with make_client(handler) as client:
            assert (await client.resolve_final_url('plain')).endswith('/plain')


class TestLifecycle:
    async def test_aclose_is_idempotent(self):
        async def handler(request: web.Request) -> web.Response:
            return web.json_response({})

        async with make_client(handler) as client:
            await client.request('seasons')
            await client.aclose()
            await client.aclose()
            # 닫힌 뒤에도 새 세션을 만들어 다시 요청할 수 있어야 한다.
            assert await client.request('seasons') == {}
