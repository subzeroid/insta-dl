from __future__ import annotations

import logging
import os
import uuid
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from ..backend import InstagramBackend
from ..exceptions import AuthError, BackendError, NotFoundError
from ..retry import retry_call
from ._hiker_map import (
    map_comment,
    map_highlight,
    map_post,
    map_profile,
    map_story,
)

_ALLOWED_HOST_SUFFIXES = (".cdninstagram.com", ".fbcdn.net")
_ALLOWED_SCHEMES = frozenset({"https"})
_MAX_REDIRECTS = 10
_DEFAULT_MAX_BYTES = 500 * 1024 * 1024

log = logging.getLogger("insta_dl.backends.hiker")

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    import httpx
    from hikerapi import AsyncClient

    from ..models import Comment, Highlight, Post, Profile, StoryItem


class HikerBackend(InstagramBackend):
    name = "hiker"

    def __init__(
        self,
        token: str | None = None,
        max_download_bytes: int = _DEFAULT_MAX_BYTES,
        show_progress: bool = True,
    ) -> None:
        from hikerapi import AsyncClient

        resolved = token or os.environ.get("HIKERAPI_TOKEN")
        if not resolved:
            raise AuthError("HikerAPI token required (pass token= or set HIKERAPI_TOKEN)")
        self._client: AsyncClient = AsyncClient(token=resolved)
        self._http: httpx.AsyncClient | None = None
        self._max_bytes = max_download_bytes
        self._show_progress = show_progress

    def _cdn(self) -> httpx.AsyncClient:
        import httpx

        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30.0, follow_redirects=False)
        return self._http

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None
        aclose = getattr(self._client, "aclose", None)
        if aclose is not None:
            await aclose()

    async def get_profile(self, username: str) -> Profile:
        raw = await retry_call(lambda: self._client.user_by_username_v2(username))
        user = (raw or {}).get("user") if isinstance(raw, dict) else None
        if not user:
            raise NotFoundError(f"profile not found: {username}")
        return map_profile(user)

    async def get_post_by_shortcode(self, shortcode: str) -> Post:
        raw = await retry_call(lambda: self._client.media_info_by_code_v2(shortcode))
        media = None
        if isinstance(raw, dict):
            media = raw.get("media_or_ad") or raw.get("media") or raw.get("response")
        if not media:
            raise NotFoundError(f"post not found: {shortcode}")
        return map_post(media)

    async def iter_user_posts(self, user_pk: str) -> AsyncIterator[Post]:
        cursor: str | None = None
        seen: set[str] = set()
        while True:
            chunk = await retry_call(
                lambda c=cursor: self._client.user_medias_chunk_v1(user_pk, end_cursor=c)  # type: ignore[misc]
            )
            items, next_cursor = _split_chunk(chunk)
            if not items:
                break
            for raw in items:
                pk = str(raw.get("pk") or "")
                if pk in seen:
                    continue
                seen.add(pk)
                yield map_post(raw)
            if not next_cursor:
                break
            cursor = next_cursor

    async def iter_user_stories(self, user_pk: str) -> AsyncIterator[StoryItem]:
        raw = await retry_call(lambda: self._client.user_stories_v2(user_pk))
        body = _unwrap(raw)
        items = body.get("items") or body.get("reel", {}).get("items") or []
        for item in items:
            yield map_story(item)

    async def iter_user_highlights(self, user_pk: str) -> AsyncIterator[Highlight]:
        raw = await retry_call(lambda: self._client.user_highlights_v2(user_pk))
        body = _unwrap(raw)
        trays = body.get("tray") or body.get("items") or []
        for item in trays:
            yield map_highlight(item)

    async def iter_highlight_items(self, highlight_pk: str) -> AsyncIterator[StoryItem]:
        raw = await retry_call(lambda: self._client.highlight_by_id_v2(id=highlight_pk))
        body = _unwrap(raw)
        items = body.get("items") or []
        for item in items:
            yield map_story(item)

    async def iter_hashtag_posts(self, tag: str) -> AsyncIterator[Post]:
        page: str | None = None
        seen: set[str] = set()
        while True:
            raw = await retry_call(
                lambda p=page: self._client.hashtag_medias_recent_v2(tag, page_id=p)  # type: ignore[misc]
            )
            sections = (raw.get("response") or {}).get("sections") or []
            page = raw.get("next_page_id")
            empty = True
            for section in sections:
                lc = section.get("layout_content") or {}
                medias = lc.get("medias") or []
                for entry in medias:
                    media = entry.get("media") or {}
                    pk = str(media.get("pk") or "")
                    if not pk or pk in seen:
                        continue
                    seen.add(pk)
                    empty = False
                    yield map_post(media)
            if not page or empty:
                break

    async def iter_post_comments(self, post_pk: str) -> AsyncIterator[Comment]:
        page: str | None = None
        while True:
            raw = await retry_call(
                lambda p=page: self._client.media_comments_v2(post_pk, page_id=p)  # type: ignore[misc]
            )
            body = _unwrap(raw)
            items = body.get("comments") or []
            for item in items:
                try:
                    yield map_comment(item)
                except ValueError as exc:
                    log.warning("skipping malformed comment on %s: %s", post_pk, exc)
            page = raw.get("next_page_id")
            if not page or not items:
                break

    async def download_resource(self, url: str, dest: Path) -> Path:
        return await retry_call(lambda: self._download_once(url, dest))

    async def _download_once(self, url: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(f"{dest.name}.{uuid.uuid4().hex}.part")
        client = self._cdn()
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
                            if int(declared) > self._max_bytes:
                                raise BackendError(
                                    f"response Content-Length {declared} exceeds max {self._max_bytes}"
                                )
                        except ValueError:
                            pass
                    total = _parse_total(declared)
                    written = 0
                    with (
                        part.open("wb") as f,
                        _progress_bar(dest.name, total, disable=not self._show_progress) as bar,
                    ):
                        async for chunk in resp.aiter_bytes():
                            written += len(chunk)
                            if written > self._max_bytes:
                                raise BackendError(
                                    f"download exceeded max {self._max_bytes} bytes"
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


def _unwrap(raw: Any) -> dict[str, Any]:
    """HikerAPI v2 wraps payloads in {'response': {...}}; v1 returns flat dict."""
    if isinstance(raw, dict) and "response" in raw and isinstance(raw["response"], dict):
        return raw["response"]
    return raw if isinstance(raw, dict) else {}


def _split_chunk(chunk: Any) -> tuple[list[dict[str, Any]], str | None]:
    """user_medias_chunk_v1 returns [items, end_cursor]."""
    if isinstance(chunk, list) and len(chunk) == 2:
        items, cursor = chunk
        return (items or []), (cursor or None)
    if isinstance(chunk, dict):
        body = _unwrap(chunk)
        return body.get("items") or [], chunk.get("next_page_id")
    return [], None
