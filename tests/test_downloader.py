from __future__ import annotations

import json
from datetime import UTC, datetime

from insta_dl.downloader import _post_to_json, _strip_query
from insta_dl.models import MediaResource, MediaType, Post


def test_strip_query_removes_signed_tokens():
    url = "https://cdn/foo.jpg?sig=abc&exp=123&tok=secret"
    assert _strip_query(url) == "https://cdn/foo.jpg"


def test_strip_query_preserves_path_and_host():
    assert _strip_query("https://cdn.example.com/path/to/file.mp4") == "https://cdn.example.com/path/to/file.mp4"


def test_strip_query_removes_fragment():
    assert _strip_query("https://cdn/foo.jpg#section") == "https://cdn/foo.jpg"


def _post(resources: list[MediaResource]) -> Post:
    return Post(
        pk="p1",
        code="ABC",
        media_type=MediaType.PHOTO,
        taken_at=datetime(2026, 4, 21, tzinfo=UTC),
        owner_pk="1",
        owner_username="foo",
        resources=resources,
    )


def test_post_to_json_strips_urls():
    post = _post([
        MediaResource(url="https://cdn/foo.jpg?sig=SECRET&exp=1", is_video=False),
        MediaResource(url="https://cdn/bar.mp4?_nc_sid=leak", is_video=True),
    ])
    data = json.loads(_post_to_json(post))
    assert data["resources"][0]["url"] == "https://cdn/foo.jpg"
    assert data["resources"][1]["url"] == "https://cdn/bar.mp4"
    assert "SECRET" not in _post_to_json(post)
    assert "_nc_sid" not in _post_to_json(post)


def test_post_to_json_serializes_enum_and_dt():
    post = _post([])
    data = json.loads(_post_to_json(post))
    assert data["media_type"] == "photo"
    assert data["taken_at"] == "2026-04-21T00:00:00+00:00"


def test_post_to_json_handles_empty_url():
    post = _post([MediaResource(url="", is_video=False)])
    data = json.loads(_post_to_json(post))
    assert data["resources"][0]["url"] == ""
