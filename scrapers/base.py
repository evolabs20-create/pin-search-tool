import logging
import random
import time
from abc import ABC, abstractmethod
from typing import List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from models import Pin

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


class BaseScraper(ABC):
    """Base scraper with session management, rate limiting, and retry logic."""

    source_name: str = ""
    base_url: str = ""

    def __init__(self, delay: float = 1.5, timeout: int = 15):
        self.delay = delay
        self.timeout = timeout
        self.session = self._build_session()
        self._last_request_time = 0.0

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        return session

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

    def fetch(self, url: str, params: Optional[dict] = None) -> Optional[str]:
        self._rate_limit()
        try:
            logger.debug(f"Fetching {url}")
            resp = self.session.get(url, params=params, timeout=self.timeout)
            self._last_request_time = time.time()
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return None

    def post(self, url: str, data: Optional[dict] = None) -> Optional[str]:
        self._rate_limit()
        try:
            logger.debug(f"POST {url}")
            resp = self.session.post(url, data=data, timeout=self.timeout)
            self._last_request_time = time.time()
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            logger.error(f"POST failed for {url}: {e}")
            return None

    @abstractmethod
    def search(self, query: str, limit: int = 20) -> List[Pin]:
        """Search by description/keyword."""

    @abstractmethod
    def lookup(self, pin_number: str, limit: int = 20) -> List[Pin]:
        """Look up by pin number."""
