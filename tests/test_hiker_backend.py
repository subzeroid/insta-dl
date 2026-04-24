from __future__ import annotations

import pytest

from insta_dl.backends.hiker import _ensure_allowed_host, _host, _split_chunk, _unwrap
from insta_dl.exceptions import BackendError


class TestHost:
    def test_extracts_hostname(self):
        assert _host("https://scontent.cdninstagram.com/x.jpg") == "scontent.cdninstagram.com"
        assert _host("http://HOST:8080/a") == "host"

    def test_empty_for_bad_url(self):
        assert _host("not a url") == ""


class TestEnsureAllowedHost:
    @pytest.mark.parametrize(
        "url",
        [
            "https://scontent-ams2-1.cdninstagram.com/v/t51/x.jpg",
            "https://video-fra3-1.fbcdn.net/v/x.mp4",
            "https://scontent.fbcdn.net/file",
            "https://anything.cdninstagram.com/path",
        ],
    )
    def test_accepts_cdn_hosts(self, url):
        _ensure_allowed_host(url)

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost:8080/a",
            "https://evil.com/cdninstagram.com/x",
            "https://cdninstagram.com.evil.com/x",
            "https://example.org/x",
            "https://127.0.0.1/x",
        ],
    )
    def test_rejects_non_cdn(self, url):
        with pytest.raises(BackendError, match="disallowed host"):
            _ensure_allowed_host(url)


class TestUnwrap:
    def test_unwraps_response_key(self):
        assert _unwrap({"response": {"foo": 1}}) == {"foo": 1}

    def test_passes_through_flat_dict(self):
        assert _unwrap({"foo": 1}) == {"foo": 1}

    def test_empty_for_non_dict(self):
        assert _unwrap(None) == {}
        assert _unwrap([]) == {}


class TestSplitChunk:
    def test_list_tuple_format(self):
        items, cursor = _split_chunk([[{"pk": "1"}], "next-abc"])
        assert len(items) == 1
        assert cursor == "next-abc"

    def test_empty_list(self):
        items, cursor = _split_chunk([[], None])
        assert items == []
        assert cursor is None

    def test_dict_format(self):
        items, cursor = _split_chunk({"response": {"items": [{"pk": "1"}]}, "next_page_id": "p2"})
        assert len(items) == 1
        assert cursor == "p2"

    def test_malformed(self):
        assert _split_chunk(None) == ([], None)
        assert _split_chunk("garbage") == ([], None)
