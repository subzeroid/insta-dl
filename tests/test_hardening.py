from __future__ import annotations

import json

import httpx
import pytest

from insta_dl.backends.hiker import HikerBackend
from insta_dl.cdn import _ensure_allowed, _ensure_allowed_scheme, _host
from insta_dl.downloader import Downloader, DownloadOptions
from insta_dl.exceptions import BackendError
from insta_dl.filestore import _sanitize, safe_component
from insta_dl.models import Comment, MediaResource, MediaType, Post
from tests.test_downloader_integration import FakeBackend, _profile, _ts

# ============ filestore.safe_component hardening ============

class TestSanitizerEdges:
    def test_strips_zero_width_space(self):
        assert "​" not in safe_component("foo​bar")
        assert safe_component("foo​bar") == "foobar"

    def test_strips_bidi_marker(self):
        assert safe_component("‮foo") == "foo"

    def test_strips_zero_width_joiner(self):
        assert safe_component("a‍z") == "az"

    def test_strips_byte_order_mark(self):
        assert safe_component("﻿foo") == "foo"

    def test_trailing_space_stripped(self):
        assert safe_component("foo ") == "foo"
        assert safe_component("foo   ") == "foo"

    def test_trailing_dot_stripped(self):
        assert safe_component("foo.") == "foo"
        assert safe_component("foo...") == "foo"

    def test_mixed_trailing_space_and_dot(self):
        assert safe_component("foo. .") == "foo"

    @pytest.mark.parametrize("name", ["CON", "PRN", "AUX", "NUL", "COM1", "COM9", "LPT1", "LPT9"])
    def test_windows_reserved_prefixed(self, name):
        out = safe_component(name)
        assert out != name
        assert out == f"_{name}"

    def test_windows_reserved_case_insensitive(self):
        assert safe_component("con") == "_con"
        assert safe_component("Con") == "_Con"

    def test_windows_reserved_with_extension_treated(self):
        # CON.txt is also reserved on Windows
        assert safe_component("CON.txt") == "_CON.txt"

    def test_windows_reserved_substring_safe(self):
        # CONFIG is fine — only exact reserved names get prefix
        assert safe_component("CONFIG") == "CONFIG"
        assert safe_component("AUXILIARY") == "AUXILIARY"


class TestFallbackSanitization:
    def test_fallback_traversal_blocked(self):
        # primary empty, fallback malicious
        assert "/" not in safe_component("", fallback="../etc/passwd")
        assert ".." not in safe_component("", fallback="../etc/passwd").rstrip("_")

    def test_fallback_also_empty_uses_ultimate(self):
        assert safe_component("", fallback="") == "untitled"
        assert safe_component("..", fallback=".") == "untitled"

    def test_fallback_with_separator_sanitized(self):
        out = safe_component("", fallback="a/b")
        assert "/" not in out
        assert out == "a_b"

    def test_fallback_reserved_name_prefixed(self):
        out = safe_component("", fallback="CON")
        assert out == "_CON"


class TestSanitizeInternal:
    def test_returns_empty_for_pure_traversal(self):
        assert _sanitize("..") == ""
        assert _sanitize(".") == ""
        assert _sanitize("...") == ""

    def test_returns_empty_for_whitespace_only(self):
        assert _sanitize("   ") == ""
        assert _sanitize("​​") == ""


# ============ host/scheme allowlist hardening ============

class TestHost:
    def test_strips_trailing_dot(self):
        assert _host("https://foo.cdninstagram.com./x") == "foo.cdninstagram.com"

    def test_lowercase(self):
        assert _host("https://SCONTENT.CDNINSTAGRAM.COM/x") == "scontent.cdninstagram.com"


class TestScheme:
    def test_https_ok(self):
        _ensure_allowed_scheme("https://x.cdninstagram.com/y")

    def test_http_rejected(self):
        with pytest.raises(BackendError, match="disallowed scheme"):
            _ensure_allowed_scheme("http://x.cdninstagram.com/y")

    def test_ftp_rejected(self):
        with pytest.raises(BackendError, match="disallowed scheme"):
            _ensure_allowed_scheme("ftp://x.cdninstagram.com/y")


class TestEnsureAllowed:
    def test_https_cdn_ok(self):
        _ensure_allowed("https://scontent-ams2-1.cdninstagram.com/x.jpg")

    def test_https_trailing_dot_host_accepted(self):
        _ensure_allowed("https://video.fbcdn.net./x.mp4")

    def test_http_cdn_rejected(self):
        with pytest.raises(BackendError, match="scheme"):
            _ensure_allowed("http://x.cdninstagram.com/y")

    def test_https_evil_host_rejected(self):
        with pytest.raises(BackendError, match="host"):
            _ensure_allowed("https://evil.com/x.jpg")


# ============ HikerBackend.download_resource hardening ============

@pytest.fixture
def backend(monkeypatch):
    monkeypatch.setenv("HIKERAPI_TOKEN", "x")
    return HikerBackend(token="x")


class TestPartUniqueness:
    async def test_concurrent_writes_get_unique_part_files(self, backend, tmp_path):
        captured: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            # snapshot all .part files at moment of request
            captured.extend(p.name for p in tmp_path.iterdir() if p.name.endswith(".part"))
            return httpx.Response(200, content=b"x" * 100, request=request)

        backend._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
        dest = tmp_path / "a.jpg"
        # sequential calls (asyncio.gather of two coros same dest)
        import asyncio
        await asyncio.gather(
            backend.download_resource("https://scontent.cdninstagram.com/a.jpg", dest),
            backend.download_resource("https://scontent.cdninstagram.com/a.jpg", dest),
        )
        # final file exists
        assert dest.read_bytes() == b"x" * 100
        # no leftover .part files
        assert not any(p.name.endswith(".part") for p in tmp_path.iterdir())


class TestSizeLimit:
    async def test_content_length_overflow_rejected(self, backend, tmp_path):
        backend._max_bytes = 100

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"x" * 50, headers={"content-length": "999"}, request=request)

        backend._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
        with pytest.raises(BackendError, match="exceeds max"):
            await backend.download_resource("https://scontent.cdninstagram.com/x.jpg", tmp_path / "x.jpg")
        assert not any(p.name.endswith(".part") for p in tmp_path.iterdir())

    async def test_streaming_overflow_rejected(self, backend, tmp_path):
        backend._max_bytes = 50

        def gen():
            yield b"x" * 200

        def handler(request: httpx.Request) -> httpx.Response:
            # streaming response, no content-length declared
            return httpx.Response(200, stream=httpx.ByteStream(b"x" * 200), request=request)

        backend._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
        with pytest.raises(BackendError, match=r"exceed(s|ed) max"):
            await backend.download_resource("https://scontent.cdninstagram.com/x.jpg", tmp_path / "x.jpg")
        assert not any(p.name.endswith(".part") for p in tmp_path.iterdir())

    async def test_under_limit_succeeds(self, backend, tmp_path):
        backend._max_bytes = 1024

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"ok" * 10, request=request)

        backend._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
        dest = tmp_path / "x.jpg"
        await backend.download_resource("https://scontent.cdninstagram.com/x.jpg", dest)
        assert dest.read_bytes() == b"ok" * 10


class TestSchemeDowngrade:
    async def test_redirect_https_to_http_rejected(self, backend, tmp_path):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.scheme == "https":
                return httpx.Response(302, headers={"location": "http://x.cdninstagram.com/y.jpg"}, request=request)
            return httpx.Response(200, content=b"pwned", request=request)

        backend._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
        with pytest.raises(BackendError, match="scheme"):
            await backend.download_resource("https://scontent.cdninstagram.com/x.jpg", tmp_path / "x.jpg")


class TestRedirectMissingLocation:
    async def test_missing_location_header_raises(self, backend, tmp_path):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={}, request=request)

        backend._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
        with pytest.raises(BackendError, match="redirect without Location"):
            await backend.download_resource("https://scontent.cdninstagram.com/x.jpg", tmp_path / "x.jpg")


class TestRedirectLoop:
    async def test_too_many_redirects(self, backend, tmp_path):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"location": str(request.url)}, request=request)

        backend._http = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)
        with pytest.raises(BackendError, match="too many redirects"):
            await backend.download_resource("https://scontent.cdninstagram.com/x.jpg", tmp_path / "x.jpg")


# ============ Sidecar traversal protection ============

class TestSidecarTraversal:
    async def test_post_code_with_traversal_sanitized_in_sidecar(self, tmp_path):
        evil_post = Post(
            pk="p1",
            code="../../escape",
            media_type=MediaType.PHOTO,
            taken_at=_ts(),
            owner_pk="42",
            owner_username="foo",
            resources=[MediaResource(url="https://cdn/x.jpg", is_video=False)],
        )
        backend = FakeBackend(_profile(), posts=[evil_post])
        await Downloader(backend, DownloadOptions(dest=tmp_path)).download_profile("foo")
        # No file or dir should appear outside tmp_path / foo
        for entry in tmp_path.iterdir():
            assert entry.name == "foo"
        # And no .json above the user dir
        for path in tmp_path.glob("**/*.json"):
            resolved = path.resolve()
            assert str(resolved).startswith(str((tmp_path / "foo").resolve()) + "/")


class TestStreamingComments:
    async def test_comments_streamed_as_valid_json_array(self, tmp_path):
        post = Post(
            pk="p1", code="ABC", media_type=MediaType.PHOTO, taken_at=_ts(),
            owner_pk="42", owner_username="foo",
            resources=[MediaResource(url="https://cdn/x.jpg", is_video=False)],
        )
        comments = [
            Comment(pk=f"c{i}", text=f"hello {i}", created_at=_ts(),
                    user_pk="9", user_username="bob")
            for i in range(5)
        ]
        backend = FakeBackend(_profile(), posts=[post], comments={"p1": comments})
        opts = DownloadOptions(dest=tmp_path, save_comments=True)
        await Downloader(backend, opts).download_profile("foo")
        cpath = tmp_path / "foo" / "2026-04-21_16-04-15_ABC_comments.json"
        data = json.loads(cpath.read_text())
        assert len(data) == 5
        assert data[0]["text"] == "hello 0"
        assert data[4]["text"] == "hello 4"

    async def test_empty_comments_valid_json(self, tmp_path):
        post = Post(
            pk="p1", code="ABC", media_type=MediaType.PHOTO, taken_at=_ts(),
            owner_pk="42", owner_username="foo",
            resources=[MediaResource(url="https://cdn/x.jpg", is_video=False)],
        )
        backend = FakeBackend(_profile(), posts=[post], comments={})
        opts = DownloadOptions(dest=tmp_path, save_comments=True)
        await Downloader(backend, opts).download_profile("foo")
        cpath = tmp_path / "foo" / "2026-04-21_16-04-15_ABC_comments.json"
        assert json.loads(cpath.read_text()) == []
