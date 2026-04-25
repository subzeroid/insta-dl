from __future__ import annotations

import pytest

from insta_dl import cli
from insta_dl.backend import InstagramBackend
from insta_dl.models import Profile


class DummyBackend(InstagramBackend):
    name = "dummy"

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.closed = False
        self.downloads: list[tuple[str, object]] = []

    async def close(self):
        self.closed = True

    async def get_profile(self, username):
        return Profile(pk="1", username=username)

    async def get_post_by_shortcode(self, shortcode):
        raise NotImplementedError

    async def iter_user_posts(self, user_pk):
        if False:
            yield  # empty async gen

    async def iter_user_stories(self, user_pk):
        if False:
            yield

    async def iter_user_highlights(self, user_pk):
        if False:
            yield

    async def iter_highlight_items(self, highlight_pk):
        if False:
            yield

    async def iter_hashtag_posts(self, tag):
        if False:
            yield

    async def iter_post_comments(self, post_pk):
        if False:
            yield

    async def download_resource(self, url, dest):
        dest.write_bytes(b"")
        return dest


@pytest.fixture
def fake_make_backend(monkeypatch):
    created: list[DummyBackend] = []

    def factory(name, **kwargs):
        b = DummyBackend(**kwargs)
        created.append(b)
        return b

    monkeypatch.setattr("insta_dl.backends.make_backend", factory)
    return created


class TestMain:
    def test_help_exits_zero(self, capsys):
        with pytest.raises(SystemExit) as exc:
            cli.build_parser().parse_args(["--help"])
        assert exc.value.code == 0

    def test_profile_flow(self, fake_make_backend, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", ["insta-dl", "--dest", str(tmp_path), "foo"])
        rc = cli.main()
        assert rc == 0
        assert fake_make_backend[0].closed is True
        assert fake_make_backend[0].kwargs.get("token") is None

    def test_hiker_token_passed(self, fake_make_backend, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", [
            "insta-dl", "--dest", str(tmp_path), "--hiker-token", "TKN", "foo",
        ])
        rc = cli.main()
        assert rc == 0
        assert fake_make_backend[0].kwargs["token"] == "TKN"

    def test_aiograpi_args_passed(self, fake_make_backend, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", [
            "insta-dl", "--backend", "aiograpi", "--login", "u", "--password", "p",
            "--session", str(tmp_path / "session.json"), "--dest", str(tmp_path), "foo",
        ])
        rc = cli.main()
        assert rc == 0
        kwargs = fake_make_backend[0].kwargs
        assert kwargs["login"] == "u"
        assert kwargs["password"] == "p"
        assert kwargs["session_path"] == tmp_path / "session.json"

    def test_latest_stamps_saved(self, fake_make_backend, tmp_path, monkeypatch):
        stamps = tmp_path / "stamps.ini"
        monkeypatch.setattr("sys.argv", [
            "insta-dl", "--dest", str(tmp_path), "--latest-stamps", str(stamps),
            "--fast-update", "foo",
        ])
        rc = cli.main()
        assert rc == 0
        # File must exist on disk and be parseable INI (atomic write-rename)
        assert stamps.exists()
        import configparser

        cp = configparser.ConfigParser()
        cp.read(stamps)
        # No new posts in DummyBackend, so no profile section yet — but file
        # must be syntactically valid INI (empty is fine)
        assert cp.sections() == [] or "foo" in cp.sections()
        # No .tmp leftover from atomic rename
        assert not list(tmp_path.glob("*.tmp"))

    def test_aiograpi_emits_friendly_error(self, tmp_path, monkeypatch, capsys):
        # No fake_make_backend — exercise the real factory + AiograpiBackend stub.
        # With the extra installed: message mentions "not yet implemented".
        # Without the extra: message points at `pip install 'instagram-dl[aiograpi]'`.
        monkeypatch.setattr("sys.argv", [
            "insta-dl", "--backend", "aiograpi", "--dest", str(tmp_path), "foo",
        ])
        rc = cli.main()
        assert rc == 2
        err = capsys.readouterr().err
        assert "not yet implemented" in err or "not installed" in err
        assert "Traceback" not in err

    def test_keyboard_interrupt_returns_130(self, fake_make_backend, tmp_path, monkeypatch):
        async def boom(*a, **kw):
            raise KeyboardInterrupt()

        monkeypatch.setattr("insta_dl.cli._run", boom)
        monkeypatch.setattr("sys.argv", ["insta-dl", "--dest", str(tmp_path), "foo"])
        rc = cli.main()
        assert rc == 130

    def test_invalid_post_filter_returns_2(self, fake_make_backend, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", [
            "insta-dl", "--dest", str(tmp_path), "--post-filter", "__import__('os')", "foo",
        ])
        rc = cli.main()
        assert rc == 2
        err = capsys.readouterr().err
        assert "invalid --post-filter" in err

    def test_max_bytes_passed_to_backend(self, fake_make_backend, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", [
            "insta-dl", "--dest", str(tmp_path), "--max-bytes", "1024", "foo",
        ])
        rc = cli.main()
        assert rc == 0
        assert fake_make_backend[0].kwargs["max_download_bytes"] == 1024

    def test_verbose_flag_runs(self, fake_make_backend, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", ["insta-dl", "--dest", str(tmp_path), "-v", "foo"])
        assert cli.main() == 0

    def test_quiet_flag_runs(self, fake_make_backend, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", ["insta-dl", "--dest", str(tmp_path), "-q", "foo"])
        assert cli.main() == 0
