# Changelog

All notable changes to insta-dl. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows [SemVer](https://semver.org/spec/v2.0.0.html). Entries from 0.1.1 onward are assembled from Conventional Commits by [release-please](https://github.com/googleapis/release-please).

## [0.1.4](https://github.com/subzeroid/insta-dl/compare/v0.1.3...v0.1.4) (2026-04-25)


### Added

* --comments-jsonl alternative format for the comments sidecar ([cb9f41b](https://github.com/subzeroid/insta-dl/commit/cb9f41be8eeaed24104678d724305ed884e5c9c3))
* **cli:** --max-bytes flag to override the 500 MB download cap ([a6a2278](https://github.com/subzeroid/insta-dl/commit/a6a2278805f679810d6766408c399bfad2137498))
* info:USERNAME target prints profile JSON to stdout ([d63d183](https://github.com/subzeroid/insta-dl/commit/d63d183df8df32dbb63e0ea00dcf36c37c199bf8))
* parallel resource downloads within a post ([a74c97a](https://github.com/subzeroid/insta-dl/commit/a74c97af0acc3a59ad94601ab9a7bfaed4036907))


### Documentation

* examples directory with three runnable Python-API scripts ([21c36d3](https://github.com/subzeroid/insta-dl/commit/21c36d385b76bdb5148a323133dcd58ceb835fc7))

## [0.1.3](https://github.com/subzeroid/insta-dl/compare/v0.1.2...v0.1.3) (2026-04-25)


### Added

* per-target run summary and --quiet/-q flag ([91d8b1d](https://github.com/subzeroid/insta-dl/commit/91d8b1d87f81ed5eb9064cae0b78fcddf8a67549))

## [0.1.2](https://github.com/subzeroid/insta-dl/compare/v0.1.1...v0.1.2) (2026-04-25)


### Added

* --dry-run and --no-progress flags ([19a8641](https://github.com/subzeroid/insta-dl/commit/19a86411480a7b59ec0842d5673b2df9044c4003))


### Documentation

* add social preview banner ([eaf0117](https://github.com/subzeroid/insta-dl/commit/eaf011797993a20169e3857917ae3d5cc6a2e7a1))
* **changelog:** clean up duplicate Unreleased sections from release-please first-run ([383eb76](https://github.com/subzeroid/insta-dl/commit/383eb76d22fd1f6e54dcfd03016f64f5a6b0ba2b))
* redesign social preview in instagrapi-style gradient banner ([d4c3a36](https://github.com/subzeroid/insta-dl/commit/d4c3a3671e66caaac03a5be495f00dcb3854439d))
* refine social preview tagline to product-benefit framing ([d053646](https://github.com/subzeroid/insta-dl/commit/d053646cb91ee4a11952d00af0e2ff7e446e4ca0))
* refresh stale references after retry, post-filter, aiograpi-extra ([322a6e6](https://github.com/subzeroid/insta-dl/commit/322a6e63ca49b3493eadc36aed0b6ebcc8e6a4cb))

## [Unreleased]

## [0.1.1] — 2026-04-24

### Added

- Download progress bar via `tqdm` on every CDN fetch. Shows filename, bytes transferred, total (when Content-Length is declared), and transfer rate. Writes to stderr; tqdm auto-suppresses on non-TTY so CI logs stay readable.

### Infra

- `pr-title.yml` validates that pull request titles follow Conventional Commits, keeping release-please's input clean.
- `.release-please-config.json`: `include-component-in-tag: false` so release-please produces plain `vX.Y.Z` tags (the tag pattern both `release.yml` and `docker.yml` listen on).

[0.1.1]: https://github.com/subzeroid/insta-dl/releases/tag/v0.1.1

## [0.1.0] — 2026-04-24

### Added

- `--version` / `-V` flag prints the installed version.
- `--post-filter EXPR` implemented. Predicate expressions are parsed into a restricted AST (no attribute access, subscription, calls, or lambdas) and evaluated against each post with `__builtins__` stripped. Names: `likes`, `comments`, `caption`, `code`, `username`, `location`, `taken_at`, `year`/`month`/`day`, `is_video`/`is_photo`/`is_album`.
- Shell completions via `argcomplete` (documented in `docs/cli-reference.md`). Activate with `eval "$(register-python-argcomplete insta-dl)"`.
- Retry/backoff for transient failures: HTTP 408/425/429/5xx and `httpx.TransportError` are retried with exponential backoff + jitter, honoring `Retry-After`. Applies to every HikerAPI API call and to CDN downloads.
- Python 3.11 / 3.12 / 3.13 / 3.14 tested in CI matrix.
- `insta_dl/py.typed` marker — PEP 561 compliance so downstream type-checkers (mypy, pyright) pick up our annotations.
- Sigstore artifact attestations on PyPI uploads.

### Changed

- **`aiograpi` is now an optional extra.** `pip install instagram-dl` installs only what the default `hiker` backend needs; users who want aiograpi run `pip install 'instagram-dl[aiograpi]'`. Drops ~40 MB from the default install (pydantic-core, orjson, moviepy) and unblocks Python 3.14 (upstream Rust deps don't build on 3.14 yet). Selecting `--backend aiograpi` without the extra fails fast with a clear install hint.
- `mypy` config flipped to `strict = true`; `ruff` rule set expanded to include `TCH`, `PTH`, `ARG`, `RET`, `C4`.
- `insta_dl.__version__` is read from installed package metadata (`importlib.metadata.version`) instead of being hardcoded — one source of truth in `pyproject.toml`.

### Infra

- `release-please` wired up (`.github/workflows/release-please.yml`): every merge to `main` updates a standing "chore(main): release X.Y.Z" PR with the next version + CHANGELOG entry derived from Conventional Commits.

[0.1.0]: https://github.com/subzeroid/insta-dl/releases/tag/v0.1.0

## [0.0.2] — 2026-04-24

### Added

- Multi-arch Docker image at `ghcr.io/subzeroid/insta-dl` (linux/amd64, linux/arm64).
- `pipx install instagram-dl` instructions for isolated CLI installs.
- Documentation page comparing insta-dl to instaloader, yt-dlp, and gallery-dl (`docs/comparison.md`).
- `SECURITY.md`, GitHub issue/PR templates, and Dependabot configuration.
- Pre-commit hook configuration (`ruff`, `mypy`, basic hygiene).
- Codecov integration on `tests` CI job.

### Changed

- Release pipeline automated via GitHub Actions + PyPI trusted publishing; a `v*` tag push builds, publishes, and attaches artifacts to the GitHub release.
- README badges now point at live PyPI/Codecov/Actions data instead of hardcoded shields.
- README links directly to the HikerAPI free-tier signup.

[0.0.2]: https://github.com/subzeroid/insta-dl/releases/tag/v0.0.2

## [0.0.1] — 2026-04-24

### Added

- Initial async-first skeleton with pluggable backend interface (`InstagramBackend` ABC).
- HikerAPI backend (`HikerBackend`) with cursor pagination, dict→DTO mapping, and streaming downloads via `httpx.AsyncClient`.
- `Downloader` facade orchestrating profile/post/hashtag/stories/highlights/comments downloads with consistent file layout.
- CLI accepting profile names, `#hashtag`, `post:SHORTCODE`, and full `instagram.com/p/...`, `/reel/`, `/tv/` URLs (case-insensitive, anchored regex against host spoofing).
- Sidecar JSON metadata per post; optional `--comments` sidecar streamed to disk.
- `--fast-update` + `--latest-stamps` for incremental archive updates (INI-backed state).
- `safe_component()` path sanitizer applied to every user-controlled component (username, owner, hashtag, highlight title, post code).
- Hardening: HTTPS-only allowlist for CDN downloads (`*.cdninstagram.com`, `*.fbcdn.net`), manual redirect loop with cap, signed-token strip from sidecar URLs, `.part` files with UUID suffixes, configurable max-download size (default 500 MB), Windows reserved-name and bidi/zero-width character handling.
- Test suite: 198 pytest cases at 95% coverage. `httpx.MockTransport` used for CDN, fake hikerapi client for upstream.
- MkDocs Material documentation site at `docs/`.

### Stubbed

- `AiograpiBackend` — interface defined, methods raise `NotImplementedError` pending an upstream sync (made an opt-in extra in 0.1.0).

[0.0.1]: https://github.com/subzeroid/insta-dl/releases/tag/v0.0.1
[Unreleased]: https://github.com/subzeroid/insta-dl/compare/v0.1.1...HEAD
