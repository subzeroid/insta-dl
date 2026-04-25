from __future__ import annotations

import asyncio

import httpx
import pytest

from insta_dl.exceptions import NotFoundError
from insta_dl.retry import retry_call, with_retry


def _http_error(status: int, retry_after: str | None = None) -> httpx.HTTPStatusError:
    headers = {"Retry-After": retry_after} if retry_after else {}
    response = httpx.Response(status, headers=headers, request=httpx.Request("GET", "https://x/"))
    return httpx.HTTPStatusError("boom", request=response.request, response=response)


class _Counter:
    def __init__(self, fail_times: int, error: BaseException):
        self.fail_times = fail_times
        self.error = error
        self.calls = 0

    async def __call__(self):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise self.error
        return "ok"


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    async def fake(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", fake)


async def test_retry_call_succeeds_after_transient_5xx():
    counter = _Counter(fail_times=2, error=_http_error(503))
    result = await retry_call(counter, base_delay=0.01, max_delay=0.01)
    assert result == "ok"
    assert counter.calls == 3


async def test_retry_call_honors_retry_after():
    counter = _Counter(fail_times=1, error=_http_error(429, retry_after="0.1"))
    result = await retry_call(counter, base_delay=0.01)
    assert result == "ok"


async def test_retry_call_retries_transport_errors():
    counter = _Counter(fail_times=2, error=httpx.ConnectError("down"))
    result = await retry_call(counter, base_delay=0.01)
    assert result == "ok"
    assert counter.calls == 3


async def test_retry_call_does_not_retry_404():
    counter = _Counter(fail_times=5, error=_http_error(404))
    with pytest.raises(httpx.HTTPStatusError):
        await retry_call(counter, max_attempts=4, base_delay=0.01)
    assert counter.calls == 1


async def test_retry_call_gives_up_after_max_attempts():
    counter = _Counter(fail_times=99, error=_http_error(500))
    with pytest.raises(httpx.HTTPStatusError):
        await retry_call(counter, max_attempts=3, base_delay=0.01)
    assert counter.calls == 3


async def test_retry_call_does_not_retry_domain_errors():
    counter = _Counter(fail_times=1, error=NotFoundError("missing"))
    with pytest.raises(NotFoundError):
        await retry_call(counter, base_delay=0.01)
    assert counter.calls == 1


async def test_retry_call_ignores_non_numeric_retry_after():
    # Spec allows HTTP-date format; we only parse numeric. Non-numeric must
    # not crash — fall back to exponential backoff.
    counter = _Counter(fail_times=1, error=_http_error(429, retry_after="Wed, 21 Oct 2026 07:28:00 GMT"))
    result = await retry_call(counter, base_delay=0.01)
    assert result == "ok"
    assert counter.calls == 2


async def test_retry_call_zero_attempts_raises_assertion():
    # Defensive: max_attempts=0 means the for-loop never runs; the trailing
    # AssertionError is the safety net that nothing falls through silently.
    counter = _Counter(fail_times=0, error=_http_error(500))
    with pytest.raises(AssertionError, match="unreachable"):
        await retry_call(counter, max_attempts=0)


async def test_with_retry_decorator_wraps():
    calls = {"n": 0}

    @with_retry(base_delay=0.01, max_attempts=3)
    async def flaky(x: int) -> int:
        calls["n"] += 1
        if calls["n"] < 2:
            raise _http_error(502)
        return x * 2

    assert await flaky(3) == 6
    assert calls["n"] == 2
