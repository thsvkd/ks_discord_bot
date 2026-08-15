"""외부 HTTP API 클라이언트.

- 세션을 매 요청마다 새로 만들지 않고 재사용한다.
- 재시도는 `aiohttp_retry`에 위임하고, 레이트 리밋(429)은 재귀 대신 루프로 처리한다.
- 상태 코드를 도메인 예외로 변환해 호출자가 HTTP 세부사항을 몰라도 되게 한다.
"""

from __future__ import annotations

import asyncio
import time
from contextlib import suppress
from enum import Enum
from types import TracebackType
from typing import Any

import aiohttp
from aiohttp_retry import ExponentialRetry, RetryClient

from ks_bot.common.errors import ApiRequestError, RateLimitError, ResourceNotFoundError
from ks_bot.logging_config import get_logger

__all__ = ['ApiClient', 'HttpMethod']

logger = get_logger(__name__)


class HttpMethod(str, Enum):
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    DELETE = 'DELETE'
    PATCH = 'PATCH'


class ApiClient:
    """재시도/레이트 리밋을 처리하는 비동기 HTTP 클라이언트."""

    MAX_RATE_LIMIT_RETRIES = 3

    def __init__(
        self,
        api_key: str,
        base_url: str,
        *,
        max_retries: int = 3,
        timeout: float = 10.0,
        rate_limit_per_minute: int = 10,
        default_headers: dict[str, str] | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.rate_limit_per_minute = rate_limit_per_minute
        self.remaining_requests = rate_limit_per_minute
        self.rate_limit_reset_timestamp = time.time()
        self._default_headers = default_headers
        self._retry_options = ExponentialRetry(attempts=max_retries)
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()

    @property
    def default_headers(self) -> dict[str, str]:
        """인증 헤더. 생성자에서 넘기면 그 값을 그대로 쓴다(인증이 없는 공개 API용)."""
        if self._default_headers is not None:
            return dict(self._default_headers)
        return {'Authorization': f'Bearer {self.api_key}', 'Accept': 'application/vnd.api+json'}

    def build_url(self, endpoint: str) -> str:
        """엔드포인트를 절대 URL로 만든다.

        이미 절대 URL이면 그대로 쓴다. 여러 호스트를 오가는 호출자가
        세션을 하나만 유지할 수 있게 하기 위함이다.
        """
        if endpoint.startswith(('http://', 'https://')):
            return endpoint
        return f'{self.base_url}/{endpoint.lstrip("/")}'

    async def __aenter__(self) -> ApiClient:
        await self._ensure_session()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def _ensure_session(self) -> aiohttp.ClientSession:
        async with self._lock:
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def aclose(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    async def _wait_for_rate_limit_reset(self) -> None:
        sleep_time = max(0.0, self.rate_limit_reset_timestamp - time.time())
        if sleep_time <= 0:
            return
        logger.warning('레이트 리밋에 걸렸습니다. %.0f초 대기합니다.', sleep_time)
        await asyncio.sleep(sleep_time)

    def _update_rate_limit(self, headers: Any) -> None:
        # 헤더 값이 없거나 형식이 다르면 기존 값을 유지한다.
        with suppress(TypeError, ValueError):
            self.remaining_requests = int(headers.get('X-RateLimit-Remaining', self.remaining_requests))
        with suppress(TypeError, ValueError):
            self.rate_limit_reset_timestamp = float(headers.get('X-RateLimit-Reset', self.rate_limit_reset_timestamp))

    async def request(
        self,
        endpoint: str,
        method: HttpMethod = HttpMethod.GET,
        header: dict | None = None,
        params: dict | None = None,
        data: dict | None = None,
        json: dict | None = None,
    ) -> dict:
        """API를 호출하고 JSON 응답을 반환한다.

        Raises:
            ResourceNotFoundError: 404 응답.
            RateLimitError: 재시도 후에도 레이트 리밋이 풀리지 않은 경우.
            ApiRequestError: 그 외 네트워크/HTTP 오류.
        """
        url = self.build_url(endpoint)
        headers = header if header is not None else self.default_headers
        session = await self._ensure_session()
        client = RetryClient(client_session=session, retry_options=self._retry_options, raise_for_status=False)

        for _attempt in range(self.MAX_RATE_LIMIT_RETRIES):
            try:
                async with client.request(method.value, url, headers=headers, params=params, json=json, data=data) as response:
                    if response.status == 429:
                        self.remaining_requests = 0
                        self.rate_limit_reset_timestamp = float(response.headers.get('X-RateLimit-Reset', time.time())) + 1
                        await self._wait_for_rate_limit_reset()
                        continue
                    if response.status == 404:
                        raise ResourceNotFoundError(f'리소스를 찾을 수 없습니다: {endpoint}')
                    if response.status >= 400:
                        raise ApiRequestError(f'API 요청 실패({response.status}): {endpoint}')

                    self._update_rate_limit(response.headers)
                    logger.debug('API 요청 성공. endpoint=%s, 남은 요청 수=%s', endpoint, self.remaining_requests)
                    return await response.json()
            except (ResourceNotFoundError, ApiRequestError):
                raise
            except asyncio.TimeoutError as e:
                raise ApiRequestError(f'API 요청 시간 초과: {endpoint}') from e
            except aiohttp.ClientError as e:
                raise ApiRequestError(f'API 요청 중 HTTP 오류가 발생했습니다: {e}') from e

        raise RateLimitError(f'레이트 리밋이 해제되지 않아 요청을 포기했습니다: {endpoint}')

    async def resolve_final_url(self, endpoint: str, header: dict | None = None) -> str:
        """리다이렉트를 따라가 최종 URL을 반환한다.

        중계 링크(예: 배포 사이트의 `/open/...`)에서 실제 스토어 주소를 얻을 때 쓴다.
        본문은 필요 없지만, 서버가 HEAD를 허용하지 않는 경우가 많아 GET으로 요청한다.

        목적지가 4xx를 주더라도 URL 자체는 유효하다. 스토어가 봇으로 의심해 403을 돌려주는
        일이 흔한데(Epic 상품 페이지가 그렇다), 그때 주소를 버리면 상품을 식별할 수 없게 된다.
        따라서 상태 코드로는 실패시키지 않고, 주소를 얻지 못한 경우에만 예외를 던진다.

        Raises:
            ApiRequestError: 네트워크 오류로 응답 자체를 받지 못한 경우.
        """
        url = self.build_url(endpoint)
        headers = header if header is not None else self.default_headers
        session = await self._ensure_session()

        try:
            async with session.get(url, headers=headers, allow_redirects=True) as response:
                if response.status >= 400:
                    logger.debug('최종 URL의 응답이 %s입니다. 주소는 그대로 사용합니다: %s', response.status, response.url)
                return str(response.url)
        except asyncio.TimeoutError as e:
            raise ApiRequestError(f'최종 URL 확인 시간 초과: {url}') from e
        except aiohttp.ClientError as e:
            raise ApiRequestError(f'최종 URL 확인 중 HTTP 오류가 발생했습니다: {e}') from e
