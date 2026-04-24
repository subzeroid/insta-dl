from __future__ import annotations

from datetime import UTC, datetime

import pytest

from insta_dl.backends._hiker_map import (
    map_comment,
    map_highlight,
    map_post,
    map_profile,
    map_story,
)
from insta_dl.models import MediaType


def test_map_profile_basic():
    p = map_profile({
        "pk": 1234,
        "pk_id": "1234",
        "username": "foo",
        "full_name": "Foo Bar",
        "media_count": 10,
        "follower_count": 100,
        "following_count": 5,
        "is_private": False,
        "is_verified": True,
        "biography": "hi",
        "profile_pic_url": "https://x/y.jpg",
    })
    assert p.pk == "1234"
    assert p.username == "foo"
    assert p.is_verified is True
    assert p.media_count == 10


def test_map_profile_coerces_int_pk():
    p = map_profile({"pk": 42, "username": "x"})
    assert p.pk == "42"
    assert isinstance(p.pk, str)


def test_map_post_photo():
    post = map_post({
        "pk": "abc",
        "code": "XYZ",
        "media_type": 1,
        "taken_at": 1700000000,
        "user": {"pk": 99, "username": "foo"},
        "caption_text": "hello",
        "thumbnail_url": "https://cdn/abc.jpg",
        "like_count": 5,
        "comment_count": 1,
    })
    assert post.media_type is MediaType.PHOTO
    assert post.code == "XYZ"
    assert post.owner_username == "foo"
    assert len(post.resources) == 1
    assert post.resources[0].url == "https://cdn/abc.jpg"
    assert post.resources[0].is_video is False


def test_map_post_video():
    post = map_post({
        "pk": "abc",
        "code": "XYZ",
        "media_type": 2,
        "taken_at": 1700000000,
        "user": {"pk": 99, "username": "foo"},
        "video_url": "https://cdn/abc.mp4",
    })
    assert post.media_type is MediaType.VIDEO
    assert post.resources[0].is_video is True
    assert post.resources[0].url == "https://cdn/abc.mp4"


def test_map_post_album():
    post = map_post({
        "pk": "a2",
        "code": "AL",
        "media_type": 8,
        "taken_at": 1700000100,
        "user": {"pk": 99, "username": "foo"},
        "carousel_media": [
            {"media_type": 1, "thumbnail_url": "https://cdn/1.jpg"},
            {"media_type": 2, "video_url": "https://cdn/2.mp4"},
        ],
    })
    assert post.media_type is MediaType.ALBUM
    assert len(post.resources) == 2
    assert post.resources[0].is_video is False
    assert post.resources[1].is_video is True


def test_map_post_iso_timestamp_with_z():
    post = map_post({
        "pk": "p1",
        "code": "C",
        "media_type": 1,
        "taken_at": "2026-04-21T16:04:15Z",
        "user": {"pk": 1, "username": "x"},
        "thumbnail_url": "https://cdn/x.jpg",
    })
    assert post.taken_at == datetime(2026, 4, 21, 16, 4, 15, tzinfo=UTC)


def test_map_post_caption_nested():
    post = map_post({
        "pk": "p1",
        "code": "C",
        "media_type": 1,
        "taken_at": 0,
        "user": {"pk": 1, "username": "x"},
        "caption": {"text": "nested caption"},
        "thumbnail_url": "https://cdn/x.jpg",
    })
    assert post.caption == "nested caption"


def test_map_post_with_location():
    post = map_post({
        "pk": "p1",
        "code": "C",
        "media_type": 1,
        "taken_at": 0,
        "user": {"pk": 1, "username": "x"},
        "thumbnail_url": "https://cdn/x.jpg",
        "location": {"name": "Berlin", "lat": 52.5, "lng": 13.4},
    })
    assert post.location_name == "Berlin"
    assert post.location_lat == 52.5


def test_map_story():
    s = map_story({
        "pk": "s1",
        "media_type": 2,
        "taken_at": 1700000000,
        "expiring_at": 1700086400,
        "user": {"pk": 99, "username": "foo"},
        "video_url": "https://cdn/s.mp4",
    })
    assert s.media_type is MediaType.VIDEO
    assert s.expiring_at is not None
    assert s.resources[0].is_video is True


def test_map_highlight():
    h = map_highlight({
        "pk": "highlight:17991",
        "title": "Travel",
        "user": {"pk": 99},
        "cover_media": {"cropped_image_version": {"url": "https://cdn/cover.jpg"}},
    })
    assert h.pk == "17991"
    assert h.title == "Travel"
    assert h.cover_url == "https://cdn/cover.jpg"


def test_map_comment_ok():
    c = map_comment({
        "pk": "c1",
        "text": "nice",
        "created_at": 1700000050,
        "user": {"pk": 9, "username": "bob"},
    })
    assert c.text == "nice"
    assert c.user_username == "bob"


def test_map_comment_created_at_utc_fallback():
    c = map_comment({
        "pk": "c1",
        "text": "hi",
        "created_at_utc": 1700000050,
        "user": {"pk": 9, "username": "bob"},
    })
    assert c.created_at == datetime.fromtimestamp(1700000050, tz=UTC)


def test_map_comment_raises_on_missing_timestamp():
    with pytest.raises(ValueError, match="has no created_at"):
        map_comment({"pk": "c1", "text": "hi", "user": {"pk": 1, "username": "x"}})
