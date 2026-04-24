# Changelog

All notable changes to insta-dl. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows [SemVer](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `--version` / `-V` flag prints the installed version.
- `--post-filter EXPR` now works. Predicate expressions are parsed into a restricted AST (no attribute access, subscription, calls, or lambdas) and evaluated against each post against a sealed namespace. Names: `likes`, `comments`, `caption`, `code`, `username`, `location`, `taken_at`, `year`/`month`/`day`, `is_video`/`is_photo`/`is_album`.
- Shell completions via `argcomplete` (documented in `docs/cli-reference.md`). `insta-dl --<TAB>` after `eval "$(register-python-argcomplete insta-dl)"`.
- Retry/backoff for transient failures: HTTP 408/425/429/5xx and `httpx.TransportError` are retried with exponential backoff + jitter, honoring `Retry-After`. Applies to every HikerAPI API call and to CDN downloads.

### Changed

- `mypy` config flipped to `strict = true`; `ruff` rule set expanded to include `TCH`, `PTH`, `ARG`, `RET`, `C4`.

[Unreleased]: https://github.com/subzeroid/insta-dl/compare/v0.0.2...HEAD

## [0.0.2] — 2026-04-24

### Added

- Multi-arch Docker image at `ghcr.io/subzeroid/insta-dl` (linux/amd64, linux/arm64).
- `pipx install instagram-dl` instructions for isolated CLI installs.
- Documentation page comparing insta-dl to instaloader, yt-dlp, and gallery-dl (`docs/comparison.md`).
- `SECURITY.md`, GitHub issue/PR templates, and Dependabot configuration.
- Pre-commit hook configuration (`ruff`, `mypy`, basic hygiene).
- Codecov integration on `tests` CI job.

### Changed

- Release pipeline is now fully automated via GitHub Actions + PyPI trusted publishing; a `v*` tag push builds, publishes, and attaches artifacts to the GitHub release.
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

- `AiograpiBackend` — interface defined, methods raise `NotImplementedError` pending an upstream sync.
- `--post-filter` — parsed but ignored; planned implementation uses AST-restricted compile (no raw `eval`).

### Known limitations

- No retry/backoff on 429 / 5xx / connection reset (relies on hikerapi defaults).
- No support for `:feed`, `:saved`, or DMs (account-bound, blocked on aiograpi).
- Comments sidecar is a single JSON array — fine for posts with thousands of comments, may want JSONL for hundreds of thousands.

[0.0.1]: https://github.com/subzeroid/insta-dl/releases/tag/v0.0.1
