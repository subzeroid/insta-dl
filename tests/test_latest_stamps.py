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
