import httpx
import pytest

from app.llm.rate_limit import RateLimited, TokenBucket


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


async def test_token_bucket_takes_tokens_when_available() -> None:
    bucket = TokenBucket(8000, clock=FakeClock())
    await bucket.acquire(4000)
    assert bucket.level == 4000


async def test_token_bucket_raises_rate_limited_with_the_wait() -> None:
    bucket = TokenBucket(6000, clock=FakeClock())  # refills 100 tokens/s
    await bucket.acquire(6000)
    with pytest.raises(RateLimited) as error:
        await bucket.acquire(4000)
    assert error.value.retry_after_seconds == pytest.approx(40)


async def test_token_bucket_refills_over_time() -> None:
    clock = FakeClock()
    bucket = TokenBucket(6000, clock=clock)
    await bucket.acquire(6000)
    clock.now = 40
    await bucket.acquire(4000)
    assert bucket.level == pytest.approx(0)


async def test_token_bucket_observe_trusts_the_remaining_tokens_header() -> None:
    bucket = TokenBucket(8000, clock=FakeClock())
    response = httpx.Response(200, headers={"x-ratelimit-remaining-tokens": "1200"})
    await bucket.observe(response)
    assert bucket.level == 1200
