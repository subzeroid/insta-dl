"""Async retry decorator for transient backend failures.

Retries on HTTP 429 / 5xx responses and network transport errors with
exponential backoff and jitter. Decorates any async callable — including
methods that internally open streaming `httpx` responses — as long as the
operation is safe to repeat (our `download_resource` cleans up its `.part`
file on exception, so re-entering with a fresh UUID suffix is fine).
"""

from __future__ import annotations

import asyncio
import logging
import random
from functools import wraps
from typing import TYPE_CHECKING, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

log = logging.getLogger("insta_dl.retry")

P = ParamSpec("P")
T = TypeVar("T")

_RETRY_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})


def _is_retryable(exc: BaseException) -> bool:
    import httpx

    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRY_STATUS
    return False


def _retry_after(exc: BaseException) -> float | None:
    import httpx

    if not isinstance(exc, httpx.HTTPStatusError):
        return None
    header = exc.response.headers.get("Retry-After")
    if not header:
        return None
    try:
        return float(header)
    except ValueError:
        return None


async def _retry_loop(
    attempt_fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int,
    base_delay: float,
    max_delay: float,
) -> T:
    for attempt in range(1, max_attempts + 1):
        try:
            return await attempt_fn()
        except Exception as exc:
            if attempt >= max_attempts or not _is_retryable(exc):
                raise
            override = _retry_after(exc)
            if override is not None:
                delay = min(override, max_delay)
            else:
                delay = min(base_delay * 2 ** (attempt - 1), max_delay)
                delay += random.uniform(0, delay * 0.25)
            log.warning(
                "transient error (%s); retry %d/%d in %.1fs",
                type(exc).__name__,
                attempt,
                max_attempts,
                delay,
            )
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")


def with_retry(
    *,
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    def decorator(fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await _retry_loop(
                lambda: fn(*args, **kwargs),
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
            )

        return wrapper

    return decorator


async def retry_call(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
) -> T:
    """Ad-hoc retry wrapper for a single coroutine expression.

    Useful inside async generators where `@with_retry` can't be applied to
    the generator itself (retrying would restart iteration).
    """
    return await _retry_loop(
        fn, max_attempts=max_attempts, base_delay=base_delay, max_delay=max_delay
    )
