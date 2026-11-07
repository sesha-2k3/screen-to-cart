"""Per-model token bucket for the free tier, where tokens per minute is the binding limit."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

import httpx

# Longer than this and the side panel would look frozen; tell the user to retry instead.
MAX_WAIT_SECONDS = 20.0


class RateLimited(Exception):
    def __init__(self, retry_after_seconds: float) -> None:
        super().__init__(f"Rate limited, retry in {retry_after_seconds:.0f}s")
        self.retry_after_seconds = retry_after_seconds


class TokenBucket:
    def __init__(
        self, tokens_per_minute: int, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.capacity = float(tokens_per_minute)
        self.level = self.capacity
        self._rate = self.capacity / 60
        self._clock = clock
        self._updated = clock()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int) -> None:
        """Take ``tokens``, sleeping up to MAX_WAIT_SECONDS; raise RateLimited beyond that."""
        async with self._lock:
            self._refill()
            wait = (tokens - self.level) / self._rate
            if wait > MAX_WAIT_SECONDS:
                raise RateLimited(wait)
            if wait > 0:
                await asyncio.sleep(wait)
                self._refill()
            self.level -= tokens

    async def observe(self, response: httpx.Response) -> None:
        """httpx response hook: trust the server's count over the local estimate."""
        remaining = response.headers.get("x-ratelimit-remaining-tokens")
        if remaining is None:
            return
        self._refill()
        self.level = min(self.capacity, float(remaining))

    def _refill(self) -> None:
        now = self._clock()
        self.level = min(self.capacity, self.level + (now - self._updated) * self._rate)
        self._updated = now


_buckets: dict[str, TokenBucket] = {}


def bucket_for(model_spec: str, tokens_per_minute: int) -> TokenBucket:
    """Return the process-wide bucket for a model; Groq limits are per model."""
    if model_spec not in _buckets:
        _buckets[model_spec] = TokenBucket(tokens_per_minute)
    return _buckets[model_spec]
