# Architecture

This page is for contributors and people embedding insta-dl as a library. End-users don't need to read it.

## Layered design

```text
┌─────────────────────────────────────────────────────┐
│ cli.py                  argparse + target dispatch  │  user-facing
├─────────────────────────────────────────────────────┤
│ Downloader              file layout, mtime,         │  business logic
│  + DownloadOptions      fast-update, sidecars       │
│  + LatestStamps         INI state                   │
├─────────────────────────────────────────────────────┤
│ DTOs (models.py)        Profile, Post, StoryItem,   │  contract
│                         Highlight, Comment,         │
│                         MediaResource, MediaType    │
├─────────────────────────────────────────────────────┤
│ InstagramBackend ABC    async iterators,            │  port
│  (backend.py)           download_resource           │
├─────────────────────────────────────────────────────┤
│ HikerBackend            httpx CDN +                 │  adapters
│  (backends/hiker.py)    hikerapi.AsyncClient        │
│ AiograpiBackend         aiograpi.Client             │
└─────────────────────────────────────────────────────┘
```

The arrow points down: each layer depends only on what's below it. Backends never see the CLI; the CLI never sees backend specifics; everything talks through DTOs at the contract layer.

## File-by-file

| File | Responsibility |
|---|---|
| `insta_dl/cli.py` | argparse, `_dispatch` (target → method on `Downloader`), `main()` (asyncio.run + KeyboardInterrupt). |
| `insta_dl/downloader.py` | `Downloader` orchestrates downloads; `DownloadOptions` carries flags; `_strip_query` + `_post_to_json` keep signed tokens out of sidecars. |
| `insta_dl/backend.py` | The `InstagramBackend` ABC. Async context manager. Iterators are `AsyncIterator[...]`. |
| `insta_dl/models.py` | DTOs as `@dataclass(slots=True)`. `MediaType` enum (`PHOTO`, `VIDEO`, `ALBUM`). |
| `insta_dl/exceptions.py` | `InstaDlError` → `BackendError` → `AuthError`/`NotFoundError`/`UnsupportedByBackendError`/`RateLimitedError`. |
| `insta_dl/filestore.py` | `safe_component()`, `post_filename()`, `apply_mtime()`, `ext_from_url()`. The hardening surface for path safety. |
| `insta_dl/latest_stamps.py` | `LatestStamps` — INI persistence for `--fast-update` cutoffs. |
| `insta_dl/backends/__init__.py` | `make_backend(name, **kw)` factory. |
| `insta_dl/backends/hiker.py` | `HikerBackend` — talks to `https://api.hikerapi.com` via the hikerapi SDK; downloads media via `httpx.AsyncClient` with explicit redirect handling, host/scheme allowlist, byte budget, UUID-suffixed `.part` files. |
| `insta_dl/backends/_hiker_map.py` | Pure functions mapping HikerAPI dicts to DTOs. No I/O. |
| `insta_dl/backends/aiograpi_backend.py` | Stub. Will mirror `HikerBackend` against `aiograpi.Client`. |

## Key design decisions

**Async-first.** All I/O is async. The CLI's only sync surface is `main()` calling `asyncio.run`. Avoids blocking the event loop and matches the async nature of `aiograpi.Client` and `hikerapi.AsyncClient`.

**Dataclasses, not pydantic.** We don't validate input. We normalize backend output. `dataclass(slots=True)` is enough and avoids the dependency.

**Lazy backend imports.** Top-level `import insta_dl.backends` does not require `hikerapi` or `aiograpi` to be installed. The actual library import happens inside the backend's `__init__`. Verified by uninstalling both: `import insta_dl.backends` still works.

**`from __future__ import annotations` everywhere.** Annotations stay as strings, so `: AsyncClient` doesn't require `hikerapi` at module load.

**One `httpx.AsyncClient` per backend instance, reused.** Created lazily on first download. Closed in `close()`.

**Manual redirect loop in `download_resource`.** httpx's `follow_redirects=True` would let an attacker (via a poisoned upstream response) redirect from a CDN host to `localhost`. We set `follow_redirects=False`, then loop ourselves, validating host + scheme on every hop.

**`.part` files use `uuid.uuid4().hex`.** Same-process same-instance same-dest concurrent downloads must not collide — `pid + id(self)` is not enough. UUID4 is.

**Sidecar URLs stripped of query.** Signed CDN tokens (`oh=`, `oe=`, `_nc_sid=`) are short-lived secrets. They don't belong in JSON written to disk and synced to backups.

**`safe_component()` runs on every user-controlled path piece — including the fallback.** A backend that returns `username=""` and falls back to `pk` doesn't get to smuggle traversal through the fallback.

**Pagination hidden inside iterators.** Callers do `async for post in backend.iter_user_posts(pk)` and don't know whether it's cursor-based, page-id, or section-extraction. The contract: `iter_user_posts` is newest-first; `Downloader.fast_update` relies on this.

**Retry/backoff lives at the adapter layer.** `insta_dl/retry.py` exposes `retry_call` (ad-hoc) and `with_retry` (decorator). `HikerBackend` wraps every `_client` API call and `download_resource` with `retry_call`; `Downloader` stays oblivious. Retries on `httpx.TransportError` and HTTP 408/425/429/5xx, with exponential backoff + jitter and `Retry-After` honoring.

## Testing strategy

- Pure logic (mappers, sanitizer, latest-stamps, models, exceptions) → 100% coverage with synthetic dicts.
- Async iterators → tested with a `FakeHiker` class that returns scripted responses, asserting the iterator extracts/dedupes/paginates correctly.
- HTTP path → tested with `httpx.MockTransport`. Covers SSRF rejection, scheme-downgrade rejection, redirect-loop limit, `Content-Length` overflow, streaming overflow, missing `Location`, `.part` cleanup, concurrent same-dest writes.
- `Downloader` integration → `FakeBackend` driving the full facade, checking file layout, mtime, sidecar JSON, comments streaming, fast-update cutoff, untrusted-username sanitization.

224 tests, 95% coverage. The 5% missed: `__main__.py` trampoline (4 lines), abstract `...` placeholders, two `if __name__ == "__main__"` lines, a few defensive-error branches.

## What changes when the schema drifts

1. `_hiker_map.py` is the only file that touches raw HikerAPI dict shapes. If a field gets renamed, change is one place.
2. `Downloader` and CLI never see raw responses — they only see normalized DTOs. They don't change.
3. New tests should be added in `tests/test_hiker_backend_http.py` reproducing the new shape.

## What changes when adding a new field to a DTO

1. Add the field to the dataclass in `models.py` (with a sensible default for backward compat).
2. Update mappers in every backend's `_*_map.py` to populate it.
3. If `Downloader` or CLI should expose it, wire it through (e.g., add a flag in `DownloadOptions` and `cli.build_parser`).
4. Add tests covering the new field on each backend.

## What changes when adding a new CLI target form

`_dispatch` in `cli.py`. Keep dispatch explicit (`#tag`, `post:`, URL regex) — avoid leading `-` (argparse conflict).
