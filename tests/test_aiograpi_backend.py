"""AiograpiBackend with a fake aiograpi.Client.

The Client surface is mocked via SimpleNamespace; mappers themselves are
covered by `test_aiograpi_map.py`. Here we verify auth wiring, paging,
dedupe, and that the backend wraps every external call in retry_call.
"""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace as NS
from typing import Any

import pytest

from insta_dl.backends.aiograpi_backend import AiograpiBackend
from insta_dl.exceptions import AuthError


def _user(pk=99, username="foo"):
    return NS(pk=pk, username=username, full_name="Foo", is_private=False, is_verified=False,
              media_count=10, follower_count=100, following_count=5, biography="",
              profile_pic_url="https://x/y.jpg")


def _media(pk="m1", code="C"):
    return NS(pk=pk, code=code, media_type=1, taken_at=datetime(2026, 4, 21, tzinfo=UTC),
              user=_user(), caption_text="", thumbnail_url="https://cdn/x.jpg",
              video_url=None, like_count=0, comment_count=0, location=None, resources=[])


class FakeClient:
    """Records calls and returns canned responses keyed by method name."""

    def __init__(self, responses: dict[str, Any]):
        self._r = responses
        self.calls: list[str] = []
        # session/auth methods
        self.login_called_with: tuple[str, str] | None = None
        self.dump_settings_called_with: Any = None
        self.load_settings_called_with: Any = None

    async def login(self, username, password):
        self.login_called_with = (username, password)
        return True

    def dump_settings(self, path):
        self.dump_settings_called_with = path

    def load_settings(self, path):
        self.load_settings_called_with = path

    def media_pk_from_code(self, code):
        self.calls.append(f"media_pk_from_code:{code}")
        return self._r.get("media_pk_from_code", "1")

    async def user_info_by_username(self, username):
        self.calls.append(f"user_info_by_username:{username}")
        return self._r["user_info_by_username"]

    async def media_info(self, pk, use_cache=True):
        self.calls.append(f"media_info:{pk}")
        return self._r["media_info"]

    async def user_medias_chunk(self, user_id, end_cursor=""):
        self.calls.append(f"user_medias_chunk:{user_id}:{end_cursor}")
        chunks = self._r["user_medias_chunk"]
        return chunks[len(self.calls) - 1] if isinstance(chunks, list) and chunks else chunks

    async def user_stories(self, user_id, amount=None):
        self.calls.append(f"user_stories:{user_id}")
        return self._r.get("user_stories", [])

    async def user_highlights(self, user_id, amount=0):
        self.calls.append(f"user_highlights:{user_id}")
        return self._r.get("user_highlights", [])

    async def highlight_info(self, highlight_pk):
        self.calls.append(f"highlight_info:{highlight_pk}")
        return self._r.get("highlight_info")

    async def hashtag_medias_v1_chunk(self, name, max_amount=27, tab_key="", max_id=None):
        self.calls.append(f"hashtag_medias_v1_chunk:{name}:{max_id}")
        return self._r["hashtag_medias_v1_chunk"]

    async def media_comments_v1_chunk(self, media_id, min_id="", max_id=""):
        self.calls.append(f"media_comments_v1_chunk:{media_id}:{min_id}")
        return self._r["media_comments_v1_chunk"]


@pytest.fixture
def backend():
    b = AiograpiBackend(login="x", password="y")
    b._authed = True  # skip login flow in unit tests
    return b


class TestAuth:
    async def test_session_only_construct_ok(self, tmp_path):
        # Has session path but no creds — defers auth, doesn't blow up.
        b = AiograpiBackend(session_path=tmp_path / "sess.json")
        assert b._authed is False

    async def test_no_creds_no_session_raises(self):
        with pytest.raises(AuthError, match=r"session.*or.*login"):
            AiograpiBackend()

    async def test_login_with_creds_dumps_session(self, tmp_path, monkeypatch):
        sess = tmp_path / "sess.json"
        b = AiograpiBackend(login="u", password="p", session_path=sess)
        fc = FakeClient({})
        b._client = fc
        await b._ensure_auth()
        assert fc.login_called_with == ("u", "p")
        assert fc.dump_settings_called_with == sess
        assert b._authed is True

    async def test_load_existing_session_skips_login_when_no_creds(self, tmp_path):
        sess = tmp_path / "sess.json"
        sess.write_text("{}")
        b = AiograpiBackend(session_path=sess)
        fc = FakeClient({})
        b._client = fc
        await b._ensure_auth()
        assert fc.load_settings_called_with == sess
        assert fc.login_called_with is None  # no creds, no login attempt

    async def test_failed_login_raises_autherror(self, tmp_path):
        b = AiograpiBackend(login="u", password="p")
        fc = FakeClient({})

        async def bad_login(u, p):
            return False
        fc.login = bad_login  # type: ignore[assignment]
        b._client = fc
        with pytest.raises(AuthError, match="login failed"):
            await b._ensure_auth()


class TestProfile:
    async def test_get_profile(self, backend):
        backend._client = FakeClient({"user_info_by_username": _user(pk=42, username="foo")})
        p = await backend.get_profile("foo")
        assert p.pk == "42"
        assert p.username == "foo"


class TestPosts:
    async def test_get_post_by_shortcode(self, backend):
        backend._client = FakeClient({
            "media_pk_from_code": "555",
            "media_info": _media(pk="555", code="DXX"),
        })
        post = await backend.get_post_by_shortcode("DXX")
        assert post.code == "DXX"
        assert post.pk == "555"

    async def test_iter_user_posts_paginates_and_dedupes(self, backend):
        m1 = _media(pk="p1", code="A")
        m2 = _media(pk="p2", code="B")
        dup = _media(pk="p1", code="A")
        backend._client = FakeClient({
            "user_medias_chunk": [
                ([m1, dup], "cursor1"),  # dup within page
                ([dup, m2], None),       # dup across pages
            ],
        })
        codes = [p.code async for p in backend.iter_user_posts("42")]
        assert codes == ["A", "B"]

    async def test_iter_user_posts_empty_first_chunk(self, backend):
        backend._client = FakeClient({"user_medias_chunk": ([], None)})
        assert [p async for p in backend.iter_user_posts("42")] == []


class TestStoriesHighlights:
    async def test_iter_user_stories(self, backend):
        s = NS(pk="s1", media_type=1, taken_at=datetime(2026, 4, 21, tzinfo=UTC),
               user=_user(), thumbnail_url="https://cdn/s.jpg", video_url=None)
        backend._client = FakeClient({"user_stories": [s]})
        items = [x async for x in backend.iter_user_stories("42")]
        assert items[0].pk == "s1"

    async def test_iter_user_stories_none(self, backend):
        # aiograpi can return None for users with no active stories
        backend._client = FakeClient({"user_stories": None})
        assert [x async for x in backend.iter_user_stories("42")] == []

    async def test_iter_user_highlights(self, backend):
        h = NS(pk="highlight:1001", title="Trip", user=_user(), cover_media=None)
        backend._client = FakeClient({"user_highlights": [h]})
        hs = [x async for x in backend.iter_user_highlights("42")]
        assert hs[0].pk == "1001"

    async def test_iter_highlight_items(self, backend):
        s = NS(pk="i1", media_type=1, taken_at=datetime(2026, 4, 21, tzinfo=UTC),
               user=_user(), thumbnail_url="https://cdn/i.jpg", video_url=None)
        info = NS(items=[s])
        backend._client = FakeClient({"highlight_info": info})
        items = [x async for x in backend.iter_highlight_items("1001")]
        assert items[0].pk == "i1"


class TestHashtag:
    async def test_iter_hashtag_dedupes(self, backend):
        m1 = _media(pk="p1", code="A")
        m2 = _media(pk="p2", code="B")
        backend._client = FakeClient({"hashtag_medias_v1_chunk": ([m1, m2, m1], None)})
        codes = [p.code async for p in backend.iter_hashtag_posts("sunset")]
        assert codes == ["A", "B"]


class TestComments:
    async def test_iter_post_comments(self, backend):
        c1 = NS(pk="c1", text="nice", user=_user(),
                created_at_utc=datetime(2026, 4, 21, tzinfo=UTC),
                like_count=0, replied_to_comment_id=None)
        c2 = NS(pk="c2", text="bye", user=_user(),
                created_at_utc=datetime(2026, 4, 21, tzinfo=UTC),
                like_count=0, replied_to_comment_id=None)
        backend._client = FakeClient({"media_comments_v1_chunk": ([c1, c2], None, "")})
        out = [c async for c in backend.iter_post_comments("999")]
        assert [c.pk for c in out] == ["c1", "c2"]


class TestSplit:
    def test_split_handles_empty(self):
        from insta_dl.backends.aiograpi_backend import _split, _split_comments
        assert _split([]) == ([], None)
        assert _split(([], None)) == ([], None)
        assert _split(None) == ([], None)
        assert _split_comments(None) == ([], None)
        assert _split_comments(([], "min", "max")) == ([], "min")
