from enum import Enum, auto
import time
from termcolor import cprint
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
        self.rate_limit_reset_timestamp = time.time()
        self.retry_options = ExponentialRetry(attempts=max_retries)

    async def wait_for_rate_limit_reset(self) -> None:
        current_time = time.time()
        while self.remaining_requests <= 0 and current_time < self.rate_limit_reset_timestamp:
            sleep_time = self.rate_limit_reset_timestamp - current_time
            print(f"\rRate limit exceeded. Waiting for {sleep_time:.0f} seconds.", end='', flush=True)
            await asyncio.sleep(1)
            current_time = time.time()
        else:
            print("\nRate limit has been reset. Continuing with the requests.")

    async def request(
        self, endpoint: str, method: HttpMethod = HttpMethod.GET, header: dict = None, params: dict = None, data: dict = None, json: dict = None
    ) -> dict:
        url = f'{self.base_url}/{endpoint}'

        async with aiohttp.ClientSession() as session:
            client = RetryClient(client_session=session, retry_options=self.retry_options, raise_for_status=False)
            try:
                async with client.request(method.value, url, headers=header, params=params, json=json, data=data) as response:
                    if response.status == 429:
                        self.remaining_requests = 0
                        self.rate_limit_reset_timestamp = float(response.headers.get('X-RateLimit-Reset', time.time())) + 1
                        await self.wait_for_rate_limit_reset()
                        return await self.request(endpoint, method, header, params, data, json)
                    elif response.status == 404:
                        raise PlayerNotFoundError_Balancer
                    else:
                        self.remaining_requests = int(response.headers.get('X-RateLimit-Remaining', self.remaining_requests))
                        self.rate_limit_reset_timestamp = float(response.headers.get('X-RateLimit-Reset', self.rate_limit_reset_timestamp))

                        cprint(f'API request success! endpoint: {endpoint}, Remaining requests: {self.remaining_requests}', 'green')
                        return await response.json()
            except aiohttp.ClientError as e:
                raise APIRequestError_Balancer(f"HTTP error occurred while API request: {e}")
            except PlayerNotFoundError_Balancer as e:
                raise e
            except Exception as e:
                raise APIRequestError_Balancer(f"Unknown error occurred: {e}")


if __name__ == "__main__":

    async def main():
        import os

        api_key = os.environ.get('PUBG_TOKEN')
        platform = 'steam'
        base_url = f'https://api.pubg.com/shards/{platform}'
        api_request_handler = APIRequestHandler(api_key=api_key, base_url=base_url)

        headers = {"Authorization": f"Bearer {api_request_handler.api_key}", "Accept": "application/vnd.api+json"}
        response = await api_request_handler.request(endpoint='seasonss', method=HttpMethod.GET, header=headers)
        print(response)

    asyncio.run(main())
