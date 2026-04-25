from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

from ..backend import InstagramBackend
from ..cdn import stream_to_file
from ..exceptions import AuthError, NotFoundError
from ..retry import retry_call
from ._hiker_map import (
    map_comment,
    map_highlight,
    map_post,
    map_profile,
    map_story,
)

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
        # `reel` is None when the user has no active stories — `body.get("reel", {})`
        # would skip the default in that case (key exists, value is None).
        reel = body.get("reel") or {}
        items = body.get("items") or reel.get("items") or []
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
        # Live shape: `response.reels` is a dict keyed by `highlight:<pk>`
        # whose value carries the actual `items`. Older shape (flat
        # `response.items`) is kept as a fallback for resilience.
        reels = body.get("reels") or {}
        reel: dict[str, Any] = reels.get(f"highlight:{highlight_pk}") or {}
        if not reel and reels:
            first: Any = next(iter(reels.values()), {})
            if isinstance(first, dict):
                reel = first
        items = reel.get("items") or body.get("items") or []
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
        return await stream_to_file(
            self._cdn(), url, dest,
            max_bytes=self._max_bytes,
            show_progress=self._show_progress,
        )


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
