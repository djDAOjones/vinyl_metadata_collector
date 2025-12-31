"""Discogs API client with simple rate limiting."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx


class DiscogsError(RuntimeError):
    """Raised when the Discogs API returns an unexpected response."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"Discogs API error {status_code}: {message}")
        self.status_code = status_code
        self.message = message


class RateLimiter:
    """Fixed-interval limiter to avoid early bursts (approximately 60 / RPM seconds between calls)."""

    def __init__(self, requests_per_minute: int = 50) -> None:
        self.requests_per_minute = max(1, requests_per_minute)
        self.min_interval = 60.0 / float(self.requests_per_minute)
        self.next_available = time.monotonic()

    def acquire(self) -> None:
        now = time.monotonic()
        if now < self.next_available:
            time.sleep(self.next_available - now)
            now = time.monotonic()
        self.next_available = now + self.min_interval


@dataclass
class DiscogsClient:
    token: str
    base_url: str = "https://api.discogs.com"
    timeout: float = 30.0
    requests_per_minute: int = 60

    def __post_init__(self) -> None:
        self._limiter = RateLimiter(self.requests_per_minute)
        self._http = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Discogs token={self.token}",
                "User-Agent": "windsurf-cli/0.1.0",
            },
            timeout=self.timeout,
        )

    def close(self) -> None:
        self._http.close()

    def get_release(self, release_id: int) -> Dict[str, Any]:
        return self._request("GET", f"/releases/{release_id}")

    def search(self, **params: Any) -> Dict[str, Any]:
        """Call /database/search with arbitrary params."""
        return self._request("GET", "/database/search", params=params)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self._limiter.acquire()
        retries = 3
        backoff = 2.0
        while True:
            response = self._http.request(method, path, params=params)
            if response.status_code == 429 and retries > 0:
                time.sleep(backoff)
                retries -= 1
                backoff *= 2
                continue
            if response.status_code >= 400:
                raise DiscogsError(response.status_code, response.text.strip())
            break
        return response.json()


__all__ = ["DiscogsClient", "DiscogsError"]
