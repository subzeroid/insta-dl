"""Pydantic-typed aiograpi models → DTO mappers.

Use SimpleNamespace as a stand-in: mappers only access attributes, not
pydantic-specific machinery, so duck-typing is fine for unit testing.

Mappers themselves don't import aiograpi (only typing-only imports), so
they're testable without the optional extra installed. Backend tests
(test_aiograpi_backend.py) need the extra.
"""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace as NS

from insta_dl.backends._aiograpi_map import (
    map_comment,
    map_highlight,
    map_post,
    map_profile,
    map_story,
)
from insta_dl.models import MediaType


def _user(pk=99, username="foo"):
    return NS(pk=pk, username=username, full_name="Foo", is_private=False, is_verified=True,
              media_count=10, follower_count=100, following_count=5, biography="bio",
              profile_pic_url="https://x/y.jpg")


def test_map_profile_basic():
    p = map_profile(_user())
    assert p.pk == "99"
    assert p.username == "foo"
    assert p.is_verified is True
    assert p.media_count == 10
    assert p.profile_pic_url == "https://x/y.jpg"


def test_map_post_photo():
    m = NS(pk="abc", code="XYZ", media_type=1,
           taken_at=datetime(2026, 4, 21, 16, 4, 15, tzinfo=UTC),
           user=_user(), caption_text="hello", thumbnail_url="https://cdn/abc.jpg",
           video_url=None, like_count=5, comment_count=1, location=None, resources=[])
    post = map_post(m)
    assert post.media_type is MediaType.PHOTO
    assert post.code == "XYZ"
    assert post.owner_username == "foo"
    assert len(post.resources) == 1
    assert post.resources[0].url == "https://cdn/abc.jpg"
    assert post.resources[0].is_video is False


def test_map_post_video():
    m = NS(pk="vid", code="V", media_type=2,
           taken_at=datetime(2026, 4, 21, tzinfo=UTC),
           user=_user(), caption_text="", thumbnail_url=None,
           video_url="https://cdn/v.mp4", like_count=0, comment_count=0,
           location=None, resources=[])
    post = map_post(m)
    assert post.media_type is MediaType.VIDEO
    assert post.resources[0].is_video is True
    assert post.resources[0].url == "https://cdn/v.mp4"


def test_map_post_album_uses_resources():
    res1 = NS(pk="r1", media_type=1, thumbnail_url="https://cdn/1.jpg", video_url=None)
    res2 = NS(pk="r2", media_type=2, thumbnail_url=None, video_url="https://cdn/2.mp4")
    m = NS(pk="a", code="AL", media_type=8,
           taken_at=datetime(2026, 4, 21, tzinfo=UTC),
           user=_user(), caption_text="", thumbnail_url=None, video_url=None,
           like_count=0, comment_count=0, location=None, resources=[res1, res2])
    post = map_post(m)
    assert post.media_type is MediaType.ALBUM
    assert [r.url for r in post.resources] == ["https://cdn/1.jpg", "https://cdn/2.mp4"]
    assert [r.is_video for r in post.resources] == [False, True]


def test_map_post_naive_datetime_gets_utc():
    naive = datetime(2026, 4, 21, 12, 0, 0)  # no tzinfo
    m = NS(pk="x", code="X", media_type=1, taken_at=naive,
           user=_user(), caption_text="", thumbnail_url="https://cdn/x.jpg",
           video_url=None, like_count=0, comment_count=0, location=None, resources=[])
    post = map_post(m)
    assert post.taken_at.tzinfo is UTC


def test_map_post_with_location():
    loc = NS(name="Berlin", lat=52.5, lng=13.4)
    m = NS(pk="x", code="X", media_type=1, taken_at=datetime(2026, 1, 1, tzinfo=UTC),
           user=_user(), caption_text="", thumbnail_url="https://cdn/x.jpg",
           video_url=None, like_count=0, comment_count=0, location=loc, resources=[])
    post = map_post(m)
    assert post.location_name == "Berlin"
    assert post.location_lat == 52.5
    assert post.location_lng == 13.4


def test_map_story_video():
    s = NS(pk="s1", media_type=2, taken_at=datetime(2026, 4, 21, tzinfo=UTC),
           user=_user(), thumbnail_url=None, video_url="https://cdn/s.mp4")
    item = map_story(s)
    assert item.media_type is MediaType.VIDEO
    assert item.resources[0].is_video is True


def test_map_highlight_strips_prefix():
    cropped = NS(url="https://cdn/cover.jpg")
    cover = NS(cropped_image_version=cropped)
    h = NS(pk="highlight:17991", title="Travel", user=_user(), cover_media=cover)
    out = map_highlight(h)
    assert out.pk == "17991"
    assert out.title == "Travel"
    assert out.cover_url == "https://cdn/cover.jpg"


def test_map_highlight_no_cover():
    h = NS(pk="100", title="Empty", user=_user(), cover_media=None)
    assert map_highlight(h).cover_url is None


def test_map_comment_basic():
    c = NS(pk="c1", text="nice", user=_user(),
           created_at_utc=datetime(2026, 4, 21, tzinfo=UTC),
           like_count=3, replied_to_comment_id=None)
    out = map_comment(c)
    assert out.text == "nice"
    assert out.user_username == "foo"
    assert out.like_count == 3
    assert out.parent_pk is None


def test_map_comment_with_parent():
    c = NS(pk="c2", text="reply", user=_user(),
           created_at_utc=datetime(2026, 4, 21, tzinfo=UTC),
           like_count=0, replied_to_comment_id="c1")
    assert map_comment(c).parent_pk == "c1"
