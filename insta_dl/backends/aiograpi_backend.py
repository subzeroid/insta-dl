from __future__ import annotations

from typing import TYPE_CHECKING

from ..backend import InstagramBackend
from ..exceptions import UnsupportedByBackendError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from ..models import Comment, Highlight, Post, Profile, StoryItem


class AiograpiBackend(InstagramBackend):
    """Stub for the aiograpi backend.

    Instantiation raises `UnsupportedByBackendError` with a clear message.
    The class exists so the factory and CLI can advertise the choice;
    implementation will land once the upstream aiograpi sync completes.
    """

    name = "aiograpi"

    def __init__(
        self,
        login: str | None = None,
        password: str | None = None,
        session_path: Path | None = None,
    ) -> None:
        raise UnsupportedByBackendError(
            "aiograpi backend is not yet implemented. Use --backend hiker for now. "
            "Track progress at https://github.com/subzeroid/insta-dl/issues"
        )

    async def close(self) -> None:  # pragma: no cover
        raise UnsupportedByBackendError("aiograpi backend is not yet implemented")

    async def get_profile(self, username: str) -> Profile:  # pragma: no cover
        raise UnsupportedByBackendError("aiograpi backend is not yet implemented")

    async def get_post_by_shortcode(self, shortcode: str) -> Post:  # pragma: no cover
        raise UnsupportedByBackendError("aiograpi backend is not yet implemented")

    async def iter_user_posts(self, user_pk: str) -> AsyncIterator[Post]:  # pragma: no cover
        raise UnsupportedByBackendError("aiograpi backend is not yet implemented")
        yield

    async def iter_user_stories(self, user_pk: str) -> AsyncIterator[StoryItem]:  # pragma: no cover
        raise UnsupportedByBackendError("aiograpi backend is not yet implemented")
        yield

    async def iter_user_highlights(self, user_pk: str) -> AsyncIterator[Highlight]:  # pragma: no cover
        raise UnsupportedByBackendError("aiograpi backend is not yet implemented")
        yield

    async def iter_highlight_items(self, highlight_pk: str) -> AsyncIterator[StoryItem]:  # pragma: no cover
        raise UnsupportedByBackendError("aiograpi backend is not yet implemented")
        yield

    async def iter_hashtag_posts(self, tag: str) -> AsyncIterator[Post]:  # pragma: no cover
        raise UnsupportedByBackendError("aiograpi backend is not yet implemented")
        yield

    async def iter_post_comments(self, post_pk: str) -> AsyncIterator[Comment]:  # pragma: no cover
        raise UnsupportedByBackendError("aiograpi backend is not yet implemented")
        yield

    async def download_resource(self, url: str, dest: Path) -> Path:  # pragma: no cover
        raise UnsupportedByBackendError("aiograpi backend is not yet implemented")
