from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from insta_dl.cli import _URL_POST_RE, _URL_PROFILE_RE, _URL_RE, _URL_STORIES_RE, _dispatch, build_parser


class TestUrlRegexes:
    @pytest.mark.parametrize(
        "url, path",
        [
            ("https://www.instagram.com/p/ABC123/", "/p/ABC123/"),
            ("https://instagram.com/foo", "/foo"),
            ("http://www.instagram.com/reel/XYZ", "/reel/XYZ"),
            ("https://instagram.com/stories/foo/", "/stories/foo/"),
            ("HTTPS://WWW.INSTAGRAM.COM/p/ABC/", "/p/ABC/"),
        ],
    )
    def test_allowed_urls(self, url, path):
        m = _URL_RE.match(url)
        assert m is not None
        assert m.group(1) == path

    @pytest.mark.parametrize(
        "url",
        [
            "https://evil.com/instagram.com/p/XYZ/",
            "https://instagram.com.evil.com/p/XYZ/",
            "ftp://instagram.com/foo",
            "not a url at all",
        ],
    )
    def test_rejects_spoof_or_wrong_scheme(self, url):
        assert _URL_RE.match(url) is None

    def test_post_re(self):
        assert _URL_POST_RE.match("/p/ABC123/").group(1) == "ABC123"
        assert _URL_POST_RE.match("/reel/X_Y-Z").group(1) == "X_Y-Z"
        assert _URL_POST_RE.match("/tv/abc").group(1) == "abc"
        assert _URL_POST_RE.match("/p/ABC/extra/") is None

    def test_profile_re(self):
        assert _URL_PROFILE_RE.match("/foo").group(1) == "foo"
        assert _URL_PROFILE_RE.match("/foo.bar_baz").group(1) == "foo.bar_baz"
        assert _URL_PROFILE_RE.match("/foo/bar") is None

    def test_stories_re(self):
        assert _URL_STORIES_RE.match("/stories/user/")
        assert _URL_STORIES_RE.match("/stories/user")
        assert _URL_STORIES_RE.match("/story/x") is None


@dataclass
class DummyDownloader:
    calls: list = field(default_factory=list)

    async def download_post(self, shortcode):
        self.calls.append(("post", shortcode))

    async def download_profile(self, username):
        self.calls.append(("profile", username))

    async def download_hashtag(self, tag):
        self.calls.append(("hashtag", tag))


class TestDispatch:
    async def test_username(self):
        d = DummyDownloader()
        await _dispatch(d, "instagram")
        assert d.calls == [("profile", "instagram")]

    async def test_hashtag(self):
        d = DummyDownloader()
        await _dispatch(d, "#sunset")
        assert d.calls == [("hashtag", "sunset")]

    async def test_post_prefix(self):
        d = DummyDownloader()
        await _dispatch(d, "post:DXZlTiKEpxw")
        assert d.calls == [("post", "DXZlTiKEpxw")]

    async def test_url_post(self):
        d = DummyDownloader()
        await _dispatch(d, "https://www.instagram.com/p/DXZlTiKEpxw/")
        assert d.calls == [("post", "DXZlTiKEpxw")]

    async def test_url_reel(self):
        d = DummyDownloader()
        await _dispatch(d, "https://www.instagram.com/reel/DXZlTiKEpxw/")
        assert d.calls == [("post", "DXZlTiKEpxw")]

    async def test_url_profile(self):
        d = DummyDownloader()
        await _dispatch(d, "https://instagram.com/foo")
        assert d.calls == [("profile", "foo")]

    async def test_stories_url_rejected(self):
        d = DummyDownloader()
        with pytest.raises(SystemExit, match="stories-by-URL"):
            await _dispatch(d, "https://instagram.com/stories/foo/")

    async def test_spoof_domain_rejected(self):
        d = DummyDownloader()
        with pytest.raises(SystemExit, match=r"not an instagram\.com URL"):
            await _dispatch(d, "https://evil.com/instagram.com/p/XYZ/")

    async def test_strips_query_and_fragment(self):
        d = DummyDownloader()
        await _dispatch(d, "https://www.instagram.com/p/DXZlTiKEpxw/?igshid=abc#section")
        assert d.calls == [("post", "DXZlTiKEpxw")]

    async def test_info_target_prints_json(self, capsys):
        from insta_dl.models import Profile

        class _Backend:
            async def get_profile(self, username):
                return Profile(pk="42", username=username, full_name="Foo Bar", media_count=7)

        class _Dl:
            backend = _Backend()

        await _dispatch(_Dl(), "info:somebody")
        out = capsys.readouterr().out
        import json as _json
        data = _json.loads(out)
        assert data["username"] == "somebody"
        assert data["pk"] == "42"
        assert data["media_count"] == 7

    async def test_unrecognized_url_path_rejected(self):
        d = DummyDownloader()
        with pytest.raises(SystemExit, match="unrecognized instagram URL path"):
            await _dispatch(d, "https://instagram.com/explore/tags/foo/bar/")


class TestParser:
    def test_help_builds(self):
        parser = build_parser()
        assert parser.prog == "insta-dl"

    def test_parses_targets(self):
        args = build_parser().parse_args(["foo", "#bar"])
        assert args.targets == ["foo", "#bar"]
        assert args.backend == "hiker"

    def test_backend_choice(self):
        args = build_parser().parse_args(["foo", "--backend", "aiograpi"])
        assert args.backend == "aiograpi"
