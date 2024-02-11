from enum import Enum, auto
from termcolor import colored
import aiohttp
import asyncio
from aiohttp_retry import RetryClient, ExponentialRetry

from ks_bot.common.error import *


class HttpMethod(Enum):
    def _generate_next_value_(name: str, start, count, last_values):
        return name.upper()

    GET = auto()
    POST = auto()
    PUT = auto()
    DELETE = auto()
    PATCH = auto()


class APIRequestHandler:
    def __init__(self, api_key: str, base_url: str, max_retries: int = 3, timeout: float = 5.0, rate_limit_per_minute: int = 10):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.rate_limit_per_minute = rate_limit_per_minute
        self.remaining_requests = rate_limit_per_minute
        self.rate_limit_reset_timestamp = asyncio.get_event_loop().time()
        self.retry_options = ExponentialRetry(attempts=max_retries)

    async def wait_for_rate_limit_reset(self) -> None:
        current_time = asyncio.get_event_loop().time()
        while self.remaining_requests <= 0 and current_time < self.rate_limit_reset_timestamp:
            sleep_time = self.rate_limit_reset_timestamp - current_time
            print(f"\rRate limit exceeded. Waiting for {sleep_time:.0f} seconds.", end='', flush=True)
            await asyncio.sleep(1)
            current_time = asyncio.get_event_loop().time()
        else:
            print("\nRate limit has been reset. Continuing with the requests.")

    async def request(
        self, endpoint: str, method: HttpMethod = HttpMethod.GET, headers: dict = None, params: dict = None, data: dict = None, json: dict = None
    ) -> dict | ErrorCode_Balancer:
        url = f'{self.base_url}/{endpoint}'
        default_headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/vnd.api+json"}
        if headers:
            default_headers.update(headers)

        async with aiohttp.ClientSession() as session:
            client = RetryClient(client_session=session, retry_options=self.retry_options, raise_for_status=False)
            try:
                async with client.request(method.value, url, headers=default_headers, params=params, json=json, data=data) as response:
                    if response.status == 429:
                        self.remaining_requests = 0
                        self.rate_limit_reset_timestamp = float(response.headers.get('X-RateLimit-Reset', asyncio.get_event_loop().time())) + 1
                        await self.wait_for_rate_limit_reset()
                        return await self.request(endpoint, method, headers, params, data, json)
                    elif response.status == 404:
                        return ErrorCode_Balancer.PLAYER_NOT_FOUND
                    else:
                        self.remaining_requests = int(response.headers.get('X-RateLimit-Remaining', self.remaining_requests))
                        self.rate_limit_reset_timestamp = float(response.headers.get('X-RateLimit-Reset', self.rate_limit_reset_timestamp))
                        return await response.json()
            except aiohttp.ClientError as e:
                print(f"HTTP error occurred: {e}")
                return ErrorCode_Balancer.API_REQUEST_ERROR


if __name__ == "__main__":

    async def main():
        import os

        api_key = os.environ.get('PUBG_TOKEN')
        platform = 'steam'
        base_url = f'https://api.pubg.com/shards/{platform}'
        api_request_handler = APIRequestHandler(api_key=api_key, base_url=base_url)

        headers = {"Authorization": f"Bearer {api_request_handler.api_key}", "Accept": "application/vnd.api+json"}
        response = await api_request_handler.request(endpoint='seasonss', method=HttpMethod.GET, headers=headers)
        print(response)

    asyncio.run(main())
