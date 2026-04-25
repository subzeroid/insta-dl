from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from insta_dl.backend import InstagramBackend
from insta_dl.downloader import Downloader, DownloadOptions
from insta_dl.latest_stamps import LatestStamps
from insta_dl.models import Comment, Highlight, MediaResource, MediaType, Post, Profile, StoryItem

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path


class FakeBackend(InstagramBackend):
    """In-memory backend that records downloads for assertions."""

    name = "fake"

    def __init__(self, profile: Profile, posts: list[Post] | None = None,
                 stories: list[StoryItem] | None = None,
                 highlights: list[tuple[Highlight, list[StoryItem]]] | None = None,
                 comments: dict[str, list[Comment]] | None = None) -> None:
        self._profile = profile
        self._posts = posts or []
        self._stories = stories or []
        self._highlights = highlights or []
        self._comments = comments or {}
        self.downloaded: list[tuple[str, Path]] = []

    async def close(self) -> None:
        pass

    async def get_profile(self, username: str) -> Profile:
        return self._profile

    async def get_post_by_shortcode(self, shortcode: str) -> Post:
        for p in self._posts:
            if p.code == shortcode:
                return p
        raise KeyError(shortcode)

    async def iter_user_posts(self, user_pk: str) -> AsyncIterator[Post]:
        for p in self._posts:
            yield p

    async def iter_user_stories(self, user_pk: str) -> AsyncIterator[StoryItem]:
        for s in self._stories:
            yield s

    async def iter_user_highlights(self, user_pk: str) -> AsyncIterator[Highlight]:
        for hl, _ in self._highlights:
            yield hl

    async def iter_highlight_items(self, highlight_pk: str) -> AsyncIterator[StoryItem]:
        for hl, items in self._highlights:
            if hl.pk == highlight_pk:
                for item in items:
                    yield item

    async def iter_hashtag_posts(self, tag: str) -> AsyncIterator[Post]:
        for p in self._posts:
            yield p

    async def iter_post_comments(self, post_pk: str) -> AsyncIterator[Comment]:
        for c in self._comments.get(post_pk, []):
            yield c

    async def download_resource(self, url: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(f"fake:{url}".encode())
        self.downloaded.append((url, dest))
        return dest


def _ts(y=2026, mo=4, d=21, h=16, mi=4, s=15):
    return datetime(y, mo, d, h, mi, s, tzinfo=UTC)


def _profile(username="foo", pk="42"):
    return Profile(pk=pk, username=username, full_name="Foo")


def _post(code="ABC", taken_at=None, resources=None, username="foo", media_type=MediaType.PHOTO):
    return Post(
        pk=code,
        code=code,
        media_type=media_type,
        taken_at=taken_at or _ts(),
        owner_pk="42",
        owner_username=username,
        resources=resources or [MediaResource(url="https://cdn/x.jpg", is_video=False)],
    )


class TestDownloadProfile:
    async def test_creates_user_dir_and_downloads(self, tmp_path):
        backend = FakeBackend(_profile(), posts=[_post()])
        d = Downloader(backend, DownloadOptions(dest=tmp_path))
        await d.download_profile("foo")

        user_dir = tmp_path / "foo"
        assert user_dir.is_dir()
        files = sorted(f.name for f in user_dir.iterdir())
        assert "2026-04-21_16-04-15_ABC.jpg" in files
        assert "2026-04-21_16-04-15_ABC.json" in files

    async def test_sidecar_contains_stripped_urls(self, tmp_path):
        backend = FakeBackend(_profile(), posts=[_post(
            resources=[MediaResource(url="https://cdn/x.jpg?sig=SECRET", is_video=False)],
        )])
        await Downloader(backend, DownloadOptions(dest=tmp_path)).download_profile("foo")
        meta = json.loads((tmp_path / "foo" / "2026-04-21_16-04-15_ABC.json").read_text())
        assert meta["resources"][0]["url"] == "https://cdn/x.jpg"
        assert "SECRET" not in (tmp_path / "foo" / "2026-04-21_16-04-15_ABC.json").read_text()

    async def test_album_saves_multiple(self, tmp_path):
        album = _post(
            media_type=MediaType.ALBUM,
            resources=[
                MediaResource(url="https://cdn/1.jpg", is_video=False),
                MediaResource(url="https://cdn/2.mp4", is_video=True),
            ],
        )
        backend = FakeBackend(_profile(), posts=[album])
        await Downloader(backend, DownloadOptions(dest=tmp_path)).download_profile("foo")
        names = sorted(f.name for f in (tmp_path / "foo").iterdir() if f.suffix != ".json")
        assert names == ["2026-04-21_16-04-15_ABC.jpg", "2026-04-21_16-04-15_ABC_1.mp4"]

    async def test_fast_update_skips_already_downloaded(self, tmp_path):
        backend = FakeBackend(_profile(), posts=[_post()])
        opts = DownloadOptions(dest=tmp_path, fast_update=True)
        await Downloader(backend, opts).download_profile("foo")
        first_download_count = len(backend.downloaded)
        await Downloader(backend, opts).download_profile("foo")
        assert len(backend.downloaded) == first_download_count

    async def test_latest_stamps_cutoff(self, tmp_path):
        old = _post(code="OLD", taken_at=_ts(mo=1))
        new = _post(code="NEW", taken_at=_ts(mo=5))
        backend = FakeBackend(_profile(), posts=[new, old])
        stamps_path = tmp_path / "stamps.ini"
        stamps = LatestStamps(stamps_path)
        stamps.set_post_timestamp("foo", _ts(mo=3))
        opts = DownloadOptions(dest=tmp_path, fast_update=True, latest_stamps=stamps)
        await Downloader(backend, opts).download_profile("foo")
        downloaded_codes = {p.name for _, p in backend.downloaded}
        assert any("NEW" in name for name in downloaded_codes)
        assert not any("OLD" in name for name in downloaded_codes)

    async def test_untrusted_username_sanitized(self, tmp_path):
        evil = _profile(username="../../escape", pk="99")
        backend = FakeBackend(evil, posts=[_post(username="../../escape")])
        await Downloader(backend, DownloadOptions(dest=tmp_path)).download_profile("../../escape")
        # Security property: every downloaded file must sit under tmp_path
        # (resolved, no symlinks, no .. escapes) and no sibling/parent dirs touched
        assert backend.downloaded
        for _, path in backend.downloaded:
            resolved = path.resolve()
            assert str(resolved).startswith(str(tmp_path.resolve()) + "/")
        # no traversal produced a directory outside tmp_path
        parent_siblings = [p for p in tmp_path.parent.iterdir() if p.name == "escape"]
        assert not parent_siblings


class TestDownloadPost:
    async def test_by_shortcode(self, tmp_path):
        backend = FakeBackend(_profile(), posts=[_post(code="ABC")])
        await Downloader(backend, DownloadOptions(dest=tmp_path)).download_post("ABC")
        assert (tmp_path / "foo" / "2026-04-21_16-04-15_ABC.jpg").exists()

    async def test_falls_back_to_pk_when_username_empty(self, tmp_path):
        p = Post(pk="p", code="C", media_type=MediaType.PHOTO, taken_at=_ts(),
                 owner_pk="999", owner_username="",
                 resources=[MediaResource(url="https://cdn/x.jpg", is_video=False)])
        backend = FakeBackend(_profile(), posts=[p])
        await Downloader(backend, DownloadOptions(dest=tmp_path)).download_post("C")
        assert (tmp_path / "999" / "2026-04-21_16-04-15_C.jpg").exists()


class TestHashtag:
    async def test_hashtag_creates_tag_dir(self, tmp_path):
        backend = FakeBackend(_profile(), posts=[_post()])
        await Downloader(backend, DownloadOptions(dest=tmp_path)).download_hashtag("sunset")
        tag_dir = tmp_path / "#sunset"
        assert tag_dir.is_dir()
        assert (tag_dir / "2026-04-21_16-04-15_ABC.jpg").exists()


class TestComments:
    async def test_comments_sidecar(self, tmp_path):
        post = _post()
        comment = Comment(pk="c1", text="nice", created_at=_ts(),
                          user_pk="9", user_username="bob")
        backend = FakeBackend(_profile(), posts=[post], comments={"ABC": [comment]})
        opts = DownloadOptions(dest=tmp_path, save_comments=True)
        await Downloader(backend, opts).download_profile("foo")
        comments_path = tmp_path / "foo" / "2026-04-21_16-04-15_ABC_comments.json"
        data = json.loads(comments_path.read_text())
        assert data[0]["text"] == "nice"
        assert data[0]["created_at"] == "2026-04-21T16:04:15+00:00"


class TestStoriesHighlights:
    async def test_stories(self, tmp_path):
        story = StoryItem(pk="s1", taken_at=_ts(), media_type=MediaType.VIDEO,
                          owner_pk="42", owner_username="foo",
                          resources=[MediaResource(url="https://cdn/s.mp4", is_video=True)])
        backend = FakeBackend(_profile(), stories=[story])
        opts = DownloadOptions(dest=tmp_path, include_stories=True)
        await Downloader(backend, opts).download_profile("foo")
        assert (tmp_path / "foo" / "stories" / "2026-04-21_16-04-15_s1.mp4").exists()

    async def test_highlights_use_pk_in_folder(self, tmp_path):
        hl_a = Highlight(pk="1001", title="Travel", owner_pk="42")
        hl_b = Highlight(pk="1002", title="Travel", owner_pk="42")  # same title, different pk
        item_a = StoryItem(pk="i1", taken_at=_ts(), media_type=MediaType.PHOTO,
                           owner_pk="42", owner_username="foo",
                           resources=[MediaResource(url="https://cdn/a.jpg", is_video=False)])
        item_b = StoryItem(pk="i2", taken_at=_ts(), media_type=MediaType.PHOTO,
                           owner_pk="42", owner_username="foo",
                           resources=[MediaResource(url="https://cdn/b.jpg", is_video=False)])
        backend = FakeBackend(_profile(), highlights=[(hl_a, [item_a]), (hl_b, [item_b])])
        opts = DownloadOptions(dest=tmp_path, include_highlights=True)
        await Downloader(backend, opts).download_profile("foo")
        hl_dir = tmp_path / "foo" / "highlights"
        names = sorted(p.name for p in hl_dir.iterdir())
        assert names == ["1001_Travel", "1002_Travel"]


class TestDryRun:
    async def test_dry_run_skips_media_and_sidecar(self, tmp_path, caplog):
        backend = FakeBackend(_profile(), posts=[_post(code="A")])
        opts = DownloadOptions(dest=tmp_path, dry_run=True)
        with caplog.at_level("INFO", logger="insta_dl"):
            await Downloader(backend, opts).download_profile("foo")
        assert backend.downloaded == []  # no CDN fetches
        assert not list((tmp_path / "foo").glob("*.json"))  # no metadata sidecar
        assert not list((tmp_path / "foo").glob("*.jpg"))  # no media
        assert any("[dry-run]" in r.message for r in caplog.records)

    async def test_dry_run_still_evaluates_filter(self, tmp_path, caplog):
        posts = [
            _post(code="KEEP"),
            _post(code="SKIP"),
        ]
        posts[0].like_count = 500
        posts[1].like_count = 5
        from insta_dl.filter_expr import compile_filter

        opts = DownloadOptions(
            dest=tmp_path,
            dry_run=True,
            post_filter=compile_filter("likes > 100"),
        )
        backend = FakeBackend(_profile(), posts=posts)
        with caplog.at_level("INFO", logger="insta_dl"):
            await Downloader(backend, opts).download_profile("foo")
        messages = " ".join(r.message for r in caplog.records)
        assert "KEEP" in messages
        assert "SKIP" not in messages
        assert backend.downloaded == []

    async def test_dry_run_skips_comments_fetch(self, tmp_path):
        comment = Comment(pk="c1", text="hi", created_at=_ts(),
                          user_pk="1", user_username="u")
        backend = FakeBackend(_profile(), posts=[_post(code="A")],
                              comments={"A": [comment]})
        opts = DownloadOptions(dest=tmp_path, dry_run=True, save_comments=True)
        await Downloader(backend, opts).download_profile("foo")
        assert not list((tmp_path / "foo").glob("*_comments.json"))


class TestMakeBackend:
    def test_unknown_backend_raises(self):
        from insta_dl.backends import make_backend

        with pytest.raises(ValueError, match="unknown backend"):
            make_backend("nonexistent")
