import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from termcolor import colored, cprint
import time
from enum import Enum, auto


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
        self.session = requests.Session()
        self.timeout = timeout
        self.rate_limit_per_minute = rate_limit_per_minute
        self.remaining_requests = rate_limit_per_minute
        self.rate_limit_reset_timestamp = time.time()
        retries = Retry(total=max_retries, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))

    def wait_for_rate_limit_reset(self):
        current_time = time.time()
        while self.remaining_requests <= 0 and current_time < self.rate_limit_reset_timestamp:
            sleep_time = self.rate_limit_reset_timestamp - current_time
            cprint(f"\rRate limit exceeded. Waiting for {sleep_time:.0f} seconds.", 'yellow', end='')
            time.sleep(1)
            current_time = time.time()
        else:
            print("\nRate limit has been reset. Continuing with the requests.")

    def request(
        self, endpoint: str, method: HttpMethod = HttpMethod.GET, headers: dict = None, params: dict = None, data: dict = None, json: dict = None
    ) -> dict:
        url = f'{self.base_url}/{endpoint}'
        default_headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/vnd.api+json"}
        if headers:
            default_headers.update(headers)

        try:
            response = self.session.request(method.value, url, headers=default_headers, params=params, json=json, data=data, timeout=self.timeout)
            if response.status_code == 429:
                # We've hit the rate limit, set remaining requests to 0 and calculate reset time
                self.remaining_requests = 0
                self.rate_limit_reset_timestamp = float(response.headers.get('X-RateLimit-Reset', time.time()))
                self.wait_for_rate_limit_reset()
                return self.request(endpoint, method, headers, params, data, json)  # Retry the request
            response.raise_for_status()
            # Update remaining requests from headers
            self.remaining_requests = int(response.headers.get('X-RateLimit-Remaining', self.remaining_requests))
            self.rate_limit_reset_timestamp = float(response.headers.get('X-RateLimit-Reset', self.rate_limit_reset_timestamp))
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
        except requests.exceptions.ConnectionError as conn_err:
            print(f"Connection error occurred: {conn_err}")
        except requests.exceptions.Timeout as timeout_err:
            print(f"Timeout error occurred: {timeout_err}")
        except requests.exceptions.RequestException as err:
            print(f"An error occurred: {err}")
        return None
