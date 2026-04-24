from __future__ import annotations

from datetime import UTC, datetime

import pytest

from insta_dl.filestore import apply_mtime, ext_from_url, post_filename, safe_component


class TestSafeComponent:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("instagram", "instagram"),
            ("foo.bar_baz", "foo.bar_baz"),
            ("ok-123", "ok-123"),
        ],
    )
    def test_passthrough_safe_names(self, raw, expected):
        assert safe_component(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        ["", "   ", ".", "..", "   ..   ", "......"],
    )
    def test_empty_and_traversal_fallback(self, raw):
        assert safe_component(raw) == "untitled"

    def test_custom_fallback(self):
        assert safe_component("", fallback="user42") == "user42"

    @pytest.mark.parametrize(
        "raw, forbidden",
        [
            ("foo/bar", "/"),
            ("foo\\bar", "\\"),
            ("a:b", ":"),
            ("a*b", "*"),
            ("a?b", "?"),
            ('a"b', '"'),
            ("a<b", "<"),
            ("a>b", ">"),
            ("a|b", "|"),
        ],
    )
    def test_replaces_path_separators(self, raw, forbidden):
        out = safe_component(raw)
        assert forbidden not in out

    def test_strips_control_chars(self):
        assert "\x00" not in safe_component("\x00nul")
        assert "\x1f" not in safe_component("\x1fctrl")

    def test_strips_leading_dots_preventing_traversal(self):
        out = safe_component("../etc/passwd")
        assert ".." not in out
        assert not out.startswith(".")

    def test_caps_length(self):
        long = "a" * 500
        assert len(safe_component(long)) == 200

    def test_coerces_non_str(self):
        assert safe_component(12345) == "12345"


class TestExtFromUrl:
    @pytest.mark.parametrize(
        "url, expected",
        [
            ("https://x/y.jpg", "jpg"),
            ("https://x/y.mp4?sig=abc", "mp4"),
            ("https://x/path/to/pic.PNG", "png"),
            ("https://x/noext", "jpg"),
            ("https://x/y.verylongextension", "jpg"),
            ("https://x/y.", "jpg"),
        ],
    )
    def test_various(self, url, expected):
        assert ext_from_url(url) == expected

    def test_custom_default(self):
        assert ext_from_url("https://x/y", default="bin") == "bin"


class TestPostFilename:
    def test_basic(self):
        ts = datetime(2026, 4, 21, 16, 4, 15, tzinfo=UTC)
        assert post_filename("ABCDE", ts, 0, "jpg") == "2026-04-21_16-04-15_ABCDE.jpg"

    def test_indexed(self):
        ts = datetime(2026, 4, 21, 16, 4, 15, tzinfo=UTC)
        assert post_filename("ABCDE", ts, 2, "mp4") == "2026-04-21_16-04-15_ABCDE_2.mp4"

    def test_sanitizes_shortcode(self):
        ts = datetime(2026, 4, 21, 16, 4, 15, tzinfo=UTC)
        assert "/" not in post_filename("../evil", ts)


class TestApplyMtime:
    def test_sets_mtime(self, tmp_path):
        f = tmp_path / "x.txt"
        f.write_text("hi")
        when = datetime(2020, 1, 1, 12, 0, 0, tzinfo=UTC)
        apply_mtime(f, when)
        assert int(f.stat().st_mtime) == int(when.timestamp())
