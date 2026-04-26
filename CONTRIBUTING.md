# Contributing to insta-dl

Thanks for considering a contribution. This document covers the dev workflow.

## Setup

```bash
git clone git@github.com:subzeroid/insta-dl.git
cd insta-dl
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev,lint]'
pip install pre-commit && pre-commit install
```

Python 3.11+ required (we use `dataclass(slots=True)`, `X | Y` unions, `datetime.fromisoformat` with `Z`). The `pre-commit install` step wires up `ruff` (format + lint) and `mypy` to run on every commit — same checks CI runs.

## Running tests

```bash
pytest                                          # all tests
pytest -k hiker                                 # subset
pytest --cov=insta_dl --cov-report=term-missing # with coverage
```

The suite is fully offline — no real HikerAPI or Instagram calls. Network is mocked via `httpx.MockTransport` and a fake hikerapi client.

Coverage targets: keep pure-logic modules at 100% (`models`, `filestore`, `exceptions`, `filter_expr`). Everything else: 93%+ — that's the CI gate, enforced by `--cov-fail-under=93` in `tests.yml`. Don't write tests for `__main__.py`.

## Project layout

```
insta_dl/
  cli.py              # argparse + target dispatch
  downloader.py       # Downloader facade (orchestrates files, mtime, fast-update)
  backend.py          # InstagramBackend ABC — async iterators
  models.py           # DTOs (Profile, Post, StoryItem, Highlight, Comment)
  filestore.py        # safe_component, post_filename, mtime
  latest_stamps.py    # INI state for --fast-update
  filter_expr.py      # AST-whitelist evaluator for --post-filter
  retry.py            # httpx-aware retry/backoff (used by both backends)
  cdn.py              # shared CDN streaming (host allowlist, .part, max_bytes)
  exceptions.py       # error hierarchy
  backends/
    hiker.py              # HikerAPI adapter (uses cdn.stream_to_file)
    _hiker_map.py         # raw dict → DTO mappers
    aiograpi_backend.py   # aiograpi adapter (uses cdn.stream_to_file)
    _aiograpi_map.py      # pydantic-typed → DTO mappers
tests/
  test_*.py           # pytest, asyncio mode = auto
docs/
  *.md                # MkDocs Material site
```

## Adding a backend

1. Implement `insta_dl.backend.InstagramBackend` in `insta_dl/backends/<name>.py`. All methods are `async`; iterators are `AsyncIterator[...]`.
2. Map raw responses to DTOs in `insta_dl/backends/_<name>_map.py`. Don't fabricate missing fields — raise `ValueError` so the caller can decide to skip.
3. Implement `download_resource(url, dest)` by delegating to `insta_dl.cdn.stream_to_file(http_client, url, dest, max_bytes=..., show_progress=...)` — that helper handles the host allowlist, https-only check, manual redirect loop, `.part` atomic rename, and byte budget. Wrap the call in `retry_call` from `insta_dl.retry` for transient-error recovery. See `HikerBackend.download_resource` or `AiograpiBackend.download_resource` for the two-line reference.
4. Register in `insta_dl/backends/__init__.py:make_backend`.
5. Add tests in `tests/test_<name>_backend.py` using `httpx.MockTransport` for the CDN and a fake client for the upstream API.

The `Downloader` facade and DTOs are backend-agnostic — never let backend-specific types leak past the adapter layer.

## Code style

- No emojis in code or docs (unless the user asked for them).
- No comments unless the *why* is non-obvious. Code should self-document via naming.
- Default to writing nothing speculative (no helpers for hypothetical future requirements).
- `from __future__ import annotations` everywhere — keeps annotations lazy and string-based.
- Lazy imports for heavy backend dependencies (`hikerapi`, `aiograpi`) — top-level import of a backend module must succeed without the upstream library installed.

## Documentation

The MkDocs site lives in `docs/`. To preview locally:

```bash
pip install -e '.[docs]'
mkdocs serve
```

Then open <http://localhost:8000>. The site auto-deploys to GitHub Pages on push to `main` via `.github/workflows/docs.yml`.

## Pull requests

- Branch from `main`, rebase before opening the PR.
- One logical change per PR.
- All tests must pass; coverage shouldn't drop more than 1%.
- Use [Conventional Commits](https://www.conventionalcommits.org/) in the commit title — `feat:`, `fix:`, `refactor:`, `docs:`, `perf:`, `test:`, `ci:`, `chore:`. `release-please` reads these to draft the next version and CHANGELOG entry, so the prefix matters.
- For new CLI flags or backend methods, update `docs/cli-reference.md` and `docs/backends.md`.

## Releases

Releases are automated via [`release-please`](https://github.com/googleapis/release-please): every push to `main` updates a "chore(main): release …" PR that collects Conventional Commits into a new version + CHANGELOG entry. Merging that PR tags the release; the tag push triggers `release.yml` which builds the wheel/sdist, publishes to PyPI via trusted publishing (OIDC, no token), and attaches the artifacts to the GitHub release. `docker.yml` simultaneously builds and pushes the multi-arch image to `ghcr.io`.

## Security

If you find a vulnerability (path traversal, SSRF bypass, signed-token leak, etc.), please open a private security advisory on GitHub rather than a public issue. See [SECURITY.md](https://github.com/subzeroid/insta-dl/blob/main/SECURITY.md) for scope and response timelines.
