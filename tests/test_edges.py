from __future__ import annotations

from datetime import UTC, datetime

import pytest

from insta_dl.backends._hiker_map import _resource_from_node, _ts, map_post, map_story
from insta_dl.models import MediaType


class TestTs:
    def test_datetime_without_tz(self):
        naive = datetime(2026, 4, 21, 16, 4, 15)
        out = _ts(naive)
        assert out.tzinfo is UTC

    def test_datetime_with_tz_preserved(self):
        aware = datetime(2026, 4, 21, tzinfo=UTC)
        assert _ts(aware) is aware

    def test_iso_without_z(self):
        assert _ts("2026-04-21T16:04:15+00:00") == datetime(2026, 4, 21, 16, 4, 15, tzinfo=UTC)

    def test_float_timestamp(self):
        assert _ts(1700000000.5).tzinfo is UTC

    def test_string_unix(self):
        assert _ts("1700000000") == datetime.fromtimestamp(1700000000, tz=UTC)

    def test_unsupported_type_raises(self):
        with pytest.raises(ValueError):
            _ts(object())


class TestResourceNode:
    def test_photo_via_image_versions2(self):
        node = {
            "media_type": 1,
            "image_versions2": {"candidates": [
                {"url": "https://cdn/best.jpg", "width": 1080},
                {"url": "https://cdn/small.jpg", "width": 320},
            ]},
        }
        r = _resource_from_node(node)
        assert r.url == "https://cdn/best.jpg"
        assert r.is_video is False

    def test_video_via_video_versions(self):
        node = {
            "media_type": 2,
            "video_versions": [{"url": "https://cdn/video.mp4"}],
        }
        r = _resource_from_node(node)
        assert r.url == "https://cdn/video.mp4"
        assert r.is_video is True

    def test_dimensions_carried(self):
        node = {"thumbnail_url": "https://x.jpg", "original_width": 1080, "original_height": 1350}
        r = _resource_from_node(node)
        assert r.width == 1080
        assert r.height == 1350


class TestMapPostFallbacks:
    def test_album_empty_carousel(self):
        post = map_post({
            "pk": "1", "code": "A", "media_type": 8, "taken_at": 0,
            "user": {"pk": 1, "username": "x"},
        })
        assert post.resources == []

    def test_default_media_type_on_missing(self):
        post = map_post({
            "pk": "1", "code": "A", "taken_at": 0,
            "user": {"pk": 1, "username": "x"},
            "thumbnail_url": "https://cdn/x.jpg",
        })
        assert post.media_type is MediaType.PHOTO


class TestMapStory:
    def test_no_expiring(self):
        s = map_story({
            "pk": "s1", "media_type": 1, "taken_at": 1700000000,
            "user": {"pk": 1, "username": "x"},
            "thumbnail_url": "https://cdn/s.jpg",
        })
        assert s.expiring_at is None


class TestMakeBackend:
    def test_hiker(self, monkeypatch):
        from insta_dl import backends

        class Stub:
            def __init__(self, **kw):
                self.kw = kw

        monkeypatch.setattr(backends, "HikerBackend", Stub)
        b = backends.make_backend("hiker", token="T")
        assert isinstance(b, Stub)
        assert b.kw == {"token": "T"}

    def test_aiograpi(self, monkeypatch):
        from insta_dl import backends

        class Stub:
            def __init__(self, **kw):
                self.kw = kw

        monkeypatch.setattr(backends, "AiograpiBackend", Stub)
        b = backends.make_backend("aiograpi", login="u")
        assert isinstance(b, Stub)
        assert b.kw == {"login": "u"}
