"""aiograpi-backed Instagram backend.

Uses an Instagram session (login or saved session file) — that means
your account is on the line, unlike the hiker backend's managed proxy.
Pluses: free, full access to whatever your account can see (private
profiles you follow, etc.). Mind the rate limits.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ..backend import InstagramBackend
from ..cdn import stream_to_file
from ..exceptions import AuthError, NotFoundError
from ..retry import retry_call
from ._aiograpi_map import (
    map_comment,
    map_highlight,
    map_post,
    map_profile,
    map_story,
)

_DEFAULT_MAX_BYTES = 500 * 1024 * 1024
_PAGE_SIZE = 50  # comments per fetch — aiograpi paginates by amount

log = logging.getLogger("insta_dl.backends.aiograpi")

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    import httpx
    from aiograpi import Client

    from ..models import Comment, Highlight, Post, Profile, StoryItem


class AiograpiBackend(InstagramBackend):
    name = "aiograpi"

    def __init__(
        self,
        login: str | None = None,
        password: str | None = None,
        session_path: Path | None = None,
        max_download_bytes: int = _DEFAULT_MAX_BYTES,
        show_progress: bool = True,
    ) -> None:
        try:
            from aiograpi import Client
        except ImportError as exc:
            raise AuthError(
                "aiograpi is not installed. Run: pip install 'instagram-dl[aiograpi]'"
            ) from exc

        if not session_path and not (login and password):
            raise AuthError(
                "aiograpi backend requires either --session FILE (saved session) "
                "or --login + --password (will create one)"
            )

        self._client: Client = Client()
        self._login = login
        self._password = password
        self._session_path = session_path
        self._authed = False
        self._http: httpx.AsyncClient | None = None
        self._max_bytes = max_download_bytes
        self._show_progress = show_progress

    async def _ensure_auth(self) -> None:
        if self._authed:
            return
        # Prefer a saved session if it exists — avoids hitting the
        # login endpoint (and its rate limit) on every run.
        if self._session_path and self._session_path.exists():
            self._client.load_settings(self._session_path)
            if self._login and self._password:
                # load_settings restores cookies but doesn't validate them;
                # set creds so relogin works if the session expired.
                ok = await self._client.login(self._login, self._password)
                if not ok:
                    raise AuthError("aiograpi: session restore + relogin both failed")
        elif self._login and self._password:
            ok = await self._client.login(self._login, self._password)
            if not ok:
                raise AuthError(f"aiograpi: login failed for {self._login!r}")
            if self._session_path:
                self._session_path.parent.mkdir(parents=True, exist_ok=True)
                self._client.dump_settings(self._session_path)
        else:
            raise AuthError("aiograpi: no session and no credentials")
        self._authed = True

    def _cdn(self) -> httpx.AsyncClient:
        import httpx

        if self._http is None:
            self._http = httpx.AsyncClient(timeout=30.0, follow_redirects=False)
        return self._http

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None
        # aiograpi.Client uses an internal aiohttp session; close it if exposed.
        for attr in ("aclose", "close"):
            closer = getattr(self._client, attr, None)
            if callable(closer):
                result = closer()
                if hasattr(result, "__await__"):
                    await result
                break

    async def get_profile(self, username: str) -> Profile:
        await self._ensure_auth()
        try:
            user = await retry_call(lambda: self._client.user_info_by_username(username))
        except Exception as exc:
            if "not found" in str(exc).lower() or "404" in str(exc):
                raise NotFoundError(f"profile not found: {username}") from exc
            raise
        return map_profile(user)

    async def get_post_by_shortcode(self, shortcode: str) -> Post:
        await self._ensure_auth()
        pk = self._client.media_pk_from_code(shortcode)
        media = await retry_call(lambda: self._client.media_info(pk))
        if media is None:
            raise NotFoundError(f"post not found: {shortcode}")
        return map_post(media)

    async def iter_user_posts(self, user_pk: str) -> AsyncIterator[Post]:
        await self._ensure_auth()
        cursor: str = ""
        seen: set[str] = set()
        while True:
            chunk = await retry_call(
                lambda c=cursor: self._client.user_medias_chunk(int(user_pk), end_cursor=c)  # type: ignore[misc]
            )
            items, next_cursor = _split(chunk)
            if not items:
                break
            for raw in items:
                pk = str(raw.pk)
                if pk in seen:
                    continue
                seen.add(pk)
                yield map_post(raw)
            if not next_cursor:
                break
            cursor = next_cursor

    async def iter_user_stories(self, user_pk: str) -> AsyncIterator[StoryItem]:
        await self._ensure_auth()
        items = await retry_call(lambda: self._client.user_stories(int(user_pk)))
        for s in items or []:
            yield map_story(s)

    async def iter_user_highlights(self, user_pk: str) -> AsyncIterator[Highlight]:
        await self._ensure_auth()
        trays = await retry_call(lambda: self._client.user_highlights(int(user_pk)))
        for h in trays or []:
            yield map_highlight(h)

    async def iter_highlight_items(self, highlight_pk: str) -> AsyncIterator[StoryItem]:
        await self._ensure_auth()
        info = await retry_call(lambda: self._client.highlight_info(highlight_pk))
        items = getattr(info, "items", None) or []
        for s in items:
            yield map_story(s)

    async def iter_hashtag_posts(self, tag: str) -> AsyncIterator[Post]:
        await self._ensure_auth()
        cursor: str | None = None
        seen: set[str] = set()
        while True:
            chunk = await retry_call(
                lambda c=cursor: self._client.hashtag_medias_v1_chunk(tag, tab_key="recent", max_id=c)  # type: ignore[misc]
            )
            items, next_cursor = _split(chunk)
            if not items:
                break
            for raw in items:
                pk = str(raw.pk)
                if pk in seen:
                    continue
                seen.add(pk)
                yield map_post(raw)
            if not next_cursor:
                break
            cursor = next_cursor

    async def iter_post_comments(self, post_pk: str) -> AsyncIterator[Comment]:
        await self._ensure_auth()
        # media_comments_v1_chunk returns (items, min_id, max_id) — both
        # cursors come back; we paginate forward with min_id (newer than).
        cursor: str = ""
        seen: set[str] = set()
        while True:
            chunk = await retry_call(
                lambda c=cursor: self._client.media_comments_v1_chunk(str(post_pk), min_id=c)  # type: ignore[misc]
            )
            items, next_cursor = _split_comments(chunk)
            if not items:
                break
            page_yielded = 0
            for raw in items:
                pk = str(raw.pk)
                if pk in seen:
                    continue
                seen.add(pk)
                page_yielded += 1
                try:
                    yield map_comment(raw)
                except (ValueError, AttributeError) as exc:
                    log.warning("skipping malformed comment on %s: %s", post_pk, exc)
            if not next_cursor or page_yielded == 0:
                break
            cursor = next_cursor

    async def download_resource(self, url: str, dest: Path) -> Path:
        return await retry_call(
            lambda: stream_to_file(
                self._cdn(), url, dest,
                max_bytes=self._max_bytes,
                show_progress=self._show_progress,
            )
        )


def _split(chunk: Any) -> tuple[list[Any], str | None]:
    """aiograpi chunk methods return Tuple[List[T], cursor_str]."""
    if isinstance(chunk, tuple) and len(chunk) == 2:
        items, cursor = chunk
        return (items or []), (cursor or None)
    if isinstance(chunk, list):
        return chunk, None
    return [], None


def _split_comments(chunk: Any) -> tuple[list[Any], str | None]:
    """`media_comments_v1_chunk` returns (items, min_id, max_id)."""
    if isinstance(chunk, tuple) and len(chunk) >= 2:
        items = chunk[0]
        cursor = chunk[1]  # min_id — paginate forward (newer than this id)
        return (items or []), (cursor or None)
    return [], None
