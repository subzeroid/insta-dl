from __future__ import annotations

from datetime import UTC, datetime, timezone

from insta_dl.latest_stamps import LatestStamps


def test_empty_returns_none(tmp_path):
    s = LatestStamps(tmp_path / "stamps.ini")
    assert s.get_post_timestamp("foo") is None
    assert s.get_story_timestamp("foo") is None


def test_roundtrip_post(tmp_path):
    path = tmp_path / "stamps.ini"
    s = LatestStamps(path)
    when = datetime(2026, 4, 21, 16, 4, 15, tzinfo=UTC)
    s.set_post_timestamp("foo", when)
    s.save()

    reloaded = LatestStamps(path)
    assert reloaded.get_post_timestamp("foo") == when


def test_roundtrip_story(tmp_path):
    path = tmp_path / "stamps.ini"
    s = LatestStamps(path)
    when = datetime(2026, 4, 21, 16, 4, 15, tzinfo=UTC)
    s.set_story_timestamp("foo", when)
    s.save()
    assert LatestStamps(path).get_story_timestamp("foo") == when


def test_saves_as_utc(tmp_path):
    from datetime import timedelta

    path = tmp_path / "stamps.ini"
    s = LatestStamps(path)
    tz = timezone(timedelta(hours=3))
    local = datetime(2026, 4, 21, 19, 4, 15, tzinfo=tz)
    s.set_post_timestamp("foo", local)
    s.save()
    # Value stored on disk should be in UTC
    content = path.read_text()
    assert "2026-04-21T16:04:15+00:00" in content


def test_multiple_profiles(tmp_path):
    path = tmp_path / "stamps.ini"
    s = LatestStamps(path)
    t1 = datetime(2026, 1, 1, tzinfo=UTC)
    t2 = datetime(2026, 2, 1, tzinfo=UTC)
    s.set_post_timestamp("foo", t1)
    s.set_post_timestamp("bar", t2)
    s.save()
    r = LatestStamps(path)
    assert r.get_post_timestamp("foo") == t1
    assert r.get_post_timestamp("bar") == t2


def test_save_failure_cleans_up_tmp(tmp_path, monkeypatch):
    """If the atomic-rename's write fails, the .tmp file must not be left behind."""
    import pytest

    path = tmp_path / "stamps.ini"
    s = LatestStamps(path)
    s.set_post_timestamp("foo", datetime(2026, 1, 1, tzinfo=UTC))

    # Force write to fail mid-save.
    real_replace = type(path).replace

    def boom(self, target):
        raise OSError("disk full")

    monkeypatch.setattr(type(path), "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        s.save()
    monkeypatch.setattr(type(path), "replace", real_replace)

    # No .tmp leftover — atomic-rename pattern's failure path must clean up.
    assert not list(tmp_path.glob("*.tmp"))
    # And the original file was never created.
    assert not path.exists()
