from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from pathlib import Path

from .models import Comment, Highlight, Post, Profile, StoryItem


class InstagramBackend(ABC):
    name: str = "base"

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def get_profile(self, username: str) -> Profile: ...

    @abstractmethod
    async def get_post_by_shortcode(self, shortcode: str) -> Post: ...

    @abstractmethod
    def iter_user_posts(self, user_pk: str) -> AsyncIterator[Post]:
        """Yield posts newest-first. Downloader.fast_update stops at the first
        post at or below the cutoff, so reverse-chronological order is load-bearing."""

    @abstractmethod
    def iter_user_stories(self, user_pk: str) -> AsyncIterator[StoryItem]: ...

    @abstractmethod
    def iter_user_highlights(self, user_pk: str) -> AsyncIterator[Highlight]: ...

    @abstractmethod
    def iter_highlight_items(self, highlight_pk: str) -> AsyncIterator[StoryItem]: ...

    @abstractmethod
    def iter_hashtag_posts(self, tag: str) -> AsyncIterator[Post]: ...

    @abstractmethod
    def iter_post_comments(self, post_pk: str) -> AsyncIterator[Comment]: ...

    @abstractmethod
    async def download_resource(self, url: str, dest: Path) -> Path: ...

    async def __aenter__(self) -> InstagramBackend:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
