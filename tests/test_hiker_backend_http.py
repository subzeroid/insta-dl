from __future__ import annotations

import httpx
import pytest

from insta_dl.backends.hiker import HikerBackend
from insta_dl.exceptions import AuthError, BackendError, NotFoundError
from insta_dl.models import MediaType


class FakeHiker:
    """Stand-in for hikerapi.AsyncClient — records calls, returns scripted responses."""

    def __init__(self, responses: dict):
        self.responses = responses
        self.calls: list[tuple[str, tuple, dict]] = []

    def _record(self, name: str):
        async def handler(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            if name not in self.responses:
                raise AssertionError(f"unexpected call: {name}")
            val = self.responses[name]
            if callable(val):
                return val(*args, **kwargs)
            if isinstance(val, list):
                return val.pop(0)
            return val

        return handler

    def __getattr__(self, name):
        return self._record(name)

    async def aclose(self):
        pass


@pytest.fixture
def backend(monkeypatch):
    """HikerBackend with a stubbed hikerapi client and a fake httpx transport."""

    # bypass real hikerapi
    monkeypatch.setenv("HIKERAPI_TOKEN", "x")
    b = HikerBackend(token="x")
    b._client = FakeHiker({})  # will be overridden per-test
    return b


class TestAuth:
    def test_missing_token_raises(self, monkeypatch):
        monkeypatch.delenv("HIKERAPI_TOKEN", raising=False)
        with pytest.raises(AuthError, match="token required"):
            HikerBackend(token=None)

    def test_token_from_env(self, monkeypatch):
        monkeypatch.setenv("HIKERAPI_TOKEN", "env-token")
        b = HikerBackend()
        assert b._client is not None


class TestGetProfile:
    async def test_happy(self, backend):
        backend._client = FakeHiker({
            "user_by_username_v2": {"user": {
                "pk": 42, "username": "foo", "full_name": "Foo",
                "is_private": False, "is_verified": True,
                "media_count": 10, "follower_count": 100,
            }},
        })
        p = await backend.get_profile("foo")
        assert p.pk == "42"
        assert p.is_verified is True

    async def test_missing_raises(self, backend):
        backend._client = FakeHiker({"user_by_username_v2": {"status": "error"}})
        with pytest.raises(NotFoundError, match="profile not found"):
            await backend.get_profile("ghost")


class TestGetPost:
    async def test_happy_media_or_ad(self, backend):
        backend._client = FakeHiker({
            "media_info_by_code_v2": {"media_or_ad": {
                "pk": "1", "code": "ABC", "media_type": 1,
                "taken_at": 1700000000,
                "user": {"pk": 1, "username": "foo"},
                "thumbnail_url": "https://cdn/x.jpg",
            }},
        })
        p = await backend.get_post_by_shortcode("ABC")
        assert p.code == "ABC"
        assert p.media_type is MediaType.PHOTO

    async def test_fallback_to_media_key(self, backend):
        backend._client = FakeHiker({
            "media_info_by_code_v2": {"media": {
                "pk": "1", "code": "ABC", "media_type": 1,
                "taken_at": 1700000000,
                "user": {"pk": 1, "username": "foo"},
                "thumbnail_url": "https://cdn/x.jpg",
            }},
        })
        p = await backend.get_post_by_shortcode("ABC")
        assert p.code == "ABC"

    async def test_missing_raises(self, backend):
        backend._client = FakeHiker({"media_info_by_code_v2": {"detail": "not found"}})
        with pytest.raises(NotFoundError):
            await backend.get_post_by_shortcode("nope")


class TestIterUserPosts:
    async def test_pagination_follows_cursor(self, backend):
        backend._client = FakeHiker({"user_medias_chunk_v1": [
            [
                [
                    {"pk": "p1", "code": "A", "media_type": 1, "taken_at": 1700000000,
                     "user": {"pk": 1, "username": "f"}, "thumbnail_url": "https://cdn/a.jpg"},
                    {"pk": "p2", "code": "B", "media_type": 1, "taken_at": 1700000100,
                     "user": {"pk": 1, "username": "f"}, "thumbnail_url": "https://cdn/b.jpg"},
                ],
                "cursor-abc",
            ],
            [
                [
                    {"pk": "p3", "code": "C", "media_type": 1, "taken_at": 1700000200,
                     "user": {"pk": 1, "username": "f"}, "thumbnail_url": "https://cdn/c.jpg"},
                ],
                None,
            ],
        ]})
        codes = [p.code async for p in backend.iter_user_posts("1")]
        assert codes == ["A", "B", "C"]

    async def test_dedup_across_pages(self, backend):
        dup = {"pk": "p1", "code": "A", "media_type": 1, "taken_at": 1700000000,
               "user": {"pk": 1, "username": "f"}, "thumbnail_url": "https://cdn/a.jpg"}
        backend._client = FakeHiker({"user_medias_chunk_v1": [
            [[dup], "cursor"],
            [[dup, {**dup, "pk": "p2", "code": "B"}], None],
        ]})
        codes = [p.code async for p in backend.iter_user_posts("1")]
        assert codes == ["A", "B"]

    async def test_empty_first_chunk(self, backend):
        backend._client = FakeHiker({"user_medias_chunk_v1": [[[], None]]})
        assert [p async for p in backend.iter_user_posts("1")] == []


class TestIterStories:
    async def test_extracts_items(self, backend):
        backend._client = FakeHiker({"user_stories_v2": {
            "response": {"items": [
                {"pk": "s1", "media_type": 1, "taken_at": 1700000000,
                 "user": {"pk": 1, "username": "f"}, "thumbnail_url": "https://cdn/a.jpg"},
            ]},
        }})
        items = [s async for s in backend.iter_user_stories("1")]
        assert len(items) == 1
        assert items[0].pk == "s1"

    async def test_no_active_stories_does_not_crash(self, backend):
        # Live shape when user has no stories: top-level `reel` key exists
        # but value is None (regression: `body.get("reel", {}).get("items")`
        # crashed because the default {} wasn't substituted).
        backend._client = FakeHiker({"user_stories_v2": {
            "broadcast": None, "reel": None, "status": "ok",
        }})
        items = [s async for s in backend.iter_user_stories("1")]
        assert items == []

    async def test_reel_with_items(self, backend):
        backend._client = FakeHiker({"user_stories_v2": {
            "reel": {"items": [
                {"pk": "s2", "media_type": 1, "taken_at": 1700000000,
                 "user": {"pk": 1, "username": "f"}, "thumbnail_url": "https://cdn/b.jpg"},
            ]},
        }})
        items = [s async for s in backend.iter_user_stories("1")]
        assert len(items) == 1
        assert items[0].pk == "s2"


class TestIterHighlights:
    async def test_tray(self, backend):
        backend._client = FakeHiker({"user_highlights_v2": {
            "response": {"tray": [
                {"pk": "highlight:1001", "title": "Travel", "user": {"pk": 1}},
            ]},
        }})
        hls = [h async for h in backend.iter_user_highlights("1")]
        assert hls[0].pk == "1001"
        assert hls[0].title == "Travel"

    async def test_highlight_items_legacy_flat_shape(self, backend):
        # Old/defensive shape: items directly under response.
        backend._client = FakeHiker({"highlight_by_id_v2": {
            "response": {"items": [
                {"pk": "i1", "media_type": 1, "taken_at": 1700000000,
                 "user": {"pk": 1, "username": "f"}, "thumbnail_url": "https://cdn/i.jpg"},
            ]},
        }})
        items = [i async for i in backend.iter_highlight_items("1001")]
        assert items[0].pk == "i1"

    async def test_highlight_items_live_reels_shape(self, backend):
        # Live shape (verified against HikerAPI 2026-04): items live under
        # response.reels["highlight:<pk>"].items, not response.items.
        backend._client = FakeHiker({"highlight_by_id_v2": {
            "response": {"reels": {"highlight:1001": {
                "id": "highlight:1001",
                "items": [
                    {"pk": "i2", "media_type": 2, "taken_at": 1700000000,
                     "user": {"pk": 1, "username": "f"}, "video_url": "https://cdn/v.mp4"},
                    {"pk": "i3", "media_type": 1, "taken_at": 1700000100,
                     "user": {"pk": 1, "username": "f"}, "thumbnail_url": "https://cdn/p.jpg"},
                ],
            }}},
        }})
        items = [i async for i in backend.iter_highlight_items("1001")]
        assert [it.pk for it in items] == ["i2", "i3"]

    async def test_highlight_items_reels_with_unexpected_key(self, backend):
        # If the keying convention changes, fall back to the first reel value.
        backend._client = FakeHiker({"highlight_by_id_v2": {
            "response": {"reels": {"some_other_key": {
                "items": [
                    {"pk": "i4", "media_type": 1, "taken_at": 1700000000,
                     "user": {"pk": 1, "username": "f"}, "thumbnail_url": "https://cdn/x.jpg"},
                ],
            }}},
        }})
        items = [i async for i in backend.iter_highlight_items("1001")]
        assert [it.pk for it in items] == ["i4"]


class TestIterComments:
    async def test_pagination(self, backend):
        backend._client = FakeHiker({"media_comments_v2": [
            {"response": {"comments": [
                {"pk": "c1", "text": "a", "created_at": 1700000000,
                 "user": {"pk": 1, "username": "x"}},
            ]}, "next_page_id": "p2"},
            {"response": {"comments": [
                {"pk": "c2", "text": "b", "created_at": 1700000100,
                 "user": {"pk": 1, "username": "y"}},
            ]}, "next_page_id": None},
        ]})
        comments = [c async for c in backend.iter_post_comments("p1")]
        assert [c.pk for c in comments] == ["c1", "c2"]

    async def test_skips_malformed_comment(self, backend, caplog):
        backend._client = FakeHiker({"media_comments_v2": {
            "response": {"comments": [
                {"pk": "c1", "text": "ok", "created_at": 1700000000,
                 "user": {"pk": 1, "username": "x"}},
                {"pk": "c2", "text": "no ts", "user": {"pk": 1, "username": "y"}},
                {"pk": "c3", "text": "also ok", "created_at": 1700000100,
                 "user": {"pk": 1, "username": "z"}},
            ]},
            "next_page_id": None,
        }})
        with caplog.at_level("WARNING", logger="insta_dl.backends.hiker"):
            ids = [c.pk async for c in backend.iter_post_comments("p1")]
        assert ids == ["c1", "c3"]
        assert any("malformed comment" in r.message for r in caplog.records)


class TestIterHashtag:
    async def test_parses_sections(self, backend):
        backend._client = FakeHiker({"hashtag_medias_recent_v2": [
            {"response": {"sections": [
                {"layout_content": {"medias": [
                    {"media": {"pk": "1", "code": "A", "media_type": 1,
                               "taken_at": 1700000000,
                               "user": {"pk": 1, "username": "f"},
                               "thumbnail_url": "https://cdn/a.jpg"}},
                ]}},
            ]}, "next_page_id": None},
        ]})
        posts = [p async for p in backend.iter_hashtag_posts("sunset")]
        assert [p.code for p in posts] == ["A"]


class TestDownloadResource:
    async def test_happy_path(self, backend, tmp_path):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"data", request=request)

        backend._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
        dest = tmp_path / "x.jpg"
        await backend.download_resource("https://scontent.cdninstagram.com/x.jpg", dest)
        assert dest.read_bytes() == b"data"
        # no leftover .part
        assert not any(p.name.endswith(".part") for p in tmp_path.iterdir())

    async def test_rejects_non_cdn_host(self, backend, tmp_path):
        backend._http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)), follow_redirects=False)
        with pytest.raises(BackendError, match="disallowed host"):
            await backend.download_resource("https://evil.com/x.jpg", tmp_path / "x.jpg")
        # .part cleaned up
        assert not any(p.name.endswith(".part") for p in tmp_path.iterdir())

    async def test_rejects_redirect_to_non_cdn(self, backend, tmp_path):
        def handler(request: httpx.Request) -> httpx.Response:
            if "cdninstagram.com" in request.url.host:
                return httpx.Response(302, headers={"location": "https://evil.com/x.jpg"}, request=request)
            return httpx.Response(200, content=b"pwned", request=request)

        backend._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
        with pytest.raises(BackendError, match="disallowed host"):
            await backend.download_resource("https://scontent.cdninstagram.com/x.jpg", tmp_path / "x.jpg")

    async def test_follows_cdn_redirect(self, backend, tmp_path):
        calls = []
        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            if str(request.url).endswith("/a.jpg"):
                return httpx.Response(302, headers={"location": "https://video.fbcdn.net/b.jpg"}, request=request)
            return httpx.Response(200, content=b"final", request=request)

        backend._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
        dest = tmp_path / "x.jpg"
        await backend.download_resource("https://scontent.cdninstagram.com/a.jpg", dest)
        assert dest.read_bytes() == b"final"
        assert len(calls) == 2

    async def test_cleans_up_part_on_error(self, backend, tmp_path):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, request=request)

        backend._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
        with pytest.raises(httpx.HTTPStatusError):
            await backend.download_resource("https://scontent.cdninstagram.com/x.jpg", tmp_path / "x.jpg")
        assert not any(p.name.endswith(".part") for p in tmp_path.iterdir())


class TestClose:
    async def test_closes_http_and_hiker(self, backend):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"", request=request)

        backend._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
        await backend.close()
        assert backend._http is None
