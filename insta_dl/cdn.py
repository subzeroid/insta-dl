"""Backend-agnostic CDN streaming with security guards.

Both `HikerBackend` and `AiograpiBackend` use this for the actual byte
movement: HTTPS-only, host allowlisted to Instagram's CDNs, manual
redirect cap (so SSRF can't ride a 30x to anywhere), Content-Length
sanity check, streaming byte cap, atomic `.part` rename, and a tqdm
progress bar.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from .exceptions import BackendError

if TYPE_CHECKING:
    from pathlib import Path

    import httpx

_ALLOWED_HOST_SUFFIXES = (".cdninstagram.com", ".fbcdn.net")
_ALLOWED_SCHEMES = frozenset({"https"})
_MAX_REDIRECTS = 10


def _host(url: str) -> str:
    raw = (urlsplit(url).hostname or "").lower()
    # tolerate trailing-dot FQDN (RFC 1034 valid: foo.cdninstagram.com.)
    return raw.rstrip(".")


def _ensure_allowed_host(url: str) -> None:
    host = _host(url)
    if not host or not any(host == s.lstrip(".") or host.endswith(s) for s in _ALLOWED_HOST_SUFFIXES):
        raise BackendError(f"refusing download from disallowed host: {host!r}")


def _ensure_allowed_scheme(url: str) -> None:
    scheme = (urlsplit(url).scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise BackendError(f"refusing download with disallowed scheme: {scheme!r}")


def _ensure_allowed(url: str) -> None:
    _ensure_allowed_scheme(url)
    _ensure_allowed_host(url)


def _parse_total(declared: str | None) -> int | None:
    if declared is None:
        return None
    try:
        return int(declared)
    except ValueError:
        return None


def _progress_bar(name: str, total: int | None, *, disable: bool = False) -> Any:
    from tqdm import tqdm

    return tqdm(
        total=total,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        desc=name,
        leave=False,
        dynamic_ncols=True,
        miniters=1,
        disable=disable,
    )


async def stream_to_file(
    client: httpx.AsyncClient,
    url: str,
    dest: Path,
    *,
    max_bytes: int,
    show_progress: bool = True,
) -> Path:
    """Download `url` to `dest` via `client`, with all safety guards.

    Caller is responsible for retry-wrapping if needed.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(f"{dest.name}.{uuid.uuid4().hex}.part")
    current = url
    try:
        for _hop in range(_MAX_REDIRECTS):
            _ensure_allowed(current)
            async with client.stream("GET", current) as resp:
                if resp.is_redirect:
                    next_url = resp.headers.get("location", "")
                    if not next_url:
                        raise BackendError(f"redirect without Location from {_host(current)}")
                    current = str(resp.url.join(next_url))
                    continue
                resp.raise_for_status()
                declared = resp.headers.get("content-length")
                if declared is not None:
                    try:
                        if int(declared) > max_bytes:
                            raise BackendError(
                                f"response Content-Length {declared} exceeds max {max_bytes}"
                            )
                    except ValueError:
                        pass
                total = _parse_total(declared)
                written = 0
                with (
                    part.open("wb") as f,
                    _progress_bar(dest.name, total, disable=not show_progress) as bar,
                ):
                    async for chunk in resp.aiter_bytes():
                        written += len(chunk)
                        if written > max_bytes:
                            raise BackendError(
                                f"download exceeded max {max_bytes} bytes"
                            )
                        f.write(chunk)
                        bar.update(len(chunk))
                break
        else:
            raise BackendError(f"too many redirects (>{_MAX_REDIRECTS}) for {_host(url)}")
        part.replace(dest)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    return dest
