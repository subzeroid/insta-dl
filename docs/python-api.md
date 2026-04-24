# Python API

Use insta-dl as a library, not just a CLI. Everything is async.

## Quick example

```python
import asyncio
from pathlib import Path

from insta_dl.backends import make_backend
from insta_dl.downloader import Downloader, DownloadOptions


async def main():
    options = DownloadOptions(dest=Path("./out"))
    async with make_backend("hiker", token="YOUR_TOKEN") as backend:
        downloader = Downloader(backend, options)
        await downloader.download_profile("instagram")


asyncio.run(main())
```

## The backend interface

`insta_dl.backend.InstagramBackend` is the abstract base every backend implements:

```python
class InstagramBackend(ABC):
    name: str

    async def close(self) -> None: ...

    async def get_profile(self, username: str) -> Profile: ...
    async def get_post_by_shortcode(self, shortcode: str) -> Post: ...

    def iter_user_posts(self, user_pk: str) -> AsyncIterator[Post]: ...
    def iter_user_stories(self, user_pk: str) -> AsyncIterator[StoryItem]: ...
    def iter_user_highlights(self, user_pk: str) -> AsyncIterator[Highlight]: ...
    def iter_highlight_items(self, highlight_pk: str) -> AsyncIterator[StoryItem]: ...
    def iter_hashtag_posts(self, tag: str) -> AsyncIterator[Post]: ...
    def iter_post_comments(self, post_pk: str) -> AsyncIterator[Comment]: ...

    async def download_resource(self, url: str, dest: Path) -> Path: ...
```

Iterators yield items lazily; pagination is hidden inside. `iter_user_posts` is contractually **newest-first** — `Downloader.fast_update` relies on this to stop at the cutoff.

The class is an async context manager. Always use `async with` (or call `await backend.close()` yourself) to release the underlying HTTP clients.

## DTOs

All defined in `insta_dl.models` as `@dataclass(slots=True)`:

```python
from insta_dl.models import (
    Profile, Post, StoryItem, Highlight, Comment,
    MediaResource, MediaType,
)
```

| DTO | Notable fields |
|---|---|
| `Profile` | `pk`, `username`, `full_name`, `is_private`, `media_count`, `follower_count`, `biography`, `profile_pic_url` |
| `Post` | `pk`, `code`, `media_type` (`MediaType` enum), `taken_at` (UTC `datetime`), `owner_pk`, `owner_username`, `caption`, `like_count`, `comment_count`, `resources: list[MediaResource]`, `location_*` |
| `StoryItem` | `pk`, `taken_at`, `expiring_at`, `media_type`, `owner_*`, `resources` |
| `Highlight` | `pk`, `title`, `owner_pk`, `cover_url` |
| `Comment` | `pk`, `text`, `created_at`, `user_pk`, `user_username`, `like_count`, `parent_pk` |
| `MediaResource` | `url`, `is_video`, `width`, `height` |

DTOs are *normalized* — backends must coerce their wire types (int pks, ISO strings with `Z`, raw enum codes) into the canonical shapes here.

## Iterating without saving

```python
async with make_backend("hiker", token=TOKEN) as backend:
    profile = await backend.get_profile("instagram")
    print(f"{profile.username}: {profile.media_count} posts")

    count = 0
    async for post in backend.iter_user_posts(profile.pk):
        count += 1
        print(f"  {post.code} ({post.media_type.value}, {post.like_count} likes)")
        if count >= 10:
            break
```

## Downloader configuration

`DownloadOptions` is a dataclass with these fields:

```python
@dataclass(slots=True)
class DownloadOptions:
    dest: Path
    fast_update: bool = False
    save_comments: bool = False
    save_metadata: bool = True
    include_stories: bool = False
    include_highlights: bool = False
    post_filter: str | None = None
    latest_stamps: LatestStamps | None = None
```

`LatestStamps` is the INI-backed state for `--fast-update`:

```python
from insta_dl.latest_stamps import LatestStamps

stamps = LatestStamps(Path("./stamps.ini"))
options = DownloadOptions(dest=Path("./out"), fast_update=True, latest_stamps=stamps)

async with make_backend("hiker", token=TOKEN) as backend:
    downloader = Downloader(backend, options)
    await downloader.download_profile("instagram")

stamps.save()  # Persist newest-seen timestamps
```

## Custom file naming

`insta_dl.filestore` exposes the helpers used internally:

```python
from insta_dl.filestore import safe_component, post_filename, ext_from_url, apply_mtime

safe_component("../../etc")             # "_etc_passwd" — sanitized, never traversal-escapes
post_filename("ABC", taken_at, 0, "jpg")  # "2026-04-21_16-04-15_ABC.jpg"
ext_from_url("https://x/y.MP4?sig=xx")    # "mp4"
apply_mtime(Path("a.mp4"), taken_at)      # sets mtime to taken_at
```

## Exceptions

`insta_dl.exceptions` has the hierarchy:

```text
InstaDlError
└── BackendError
    ├── AuthError              — missing/wrong token, login failed
    ├── NotFoundError          — profile / post does not exist
    ├── UnsupportedByBackendError — feature not available for this backend
    └── RateLimitedError       — 429 from upstream (no retry yet)
```

Catch the broad `BackendError` for transport-level problems; the more specific subclasses for actionable cases.

## Implementing your own backend

Subclass `InstagramBackend` and implement every abstract method. The contract:

- All iterators are real async generators (use `async def` + `yield`); they're allowed to raise `BackendError` mid-stream.
- `iter_user_posts` MUST yield newest-first.
- `download_resource(url, dest)` MUST: validate the host (allowlist), validate the scheme (HTTPS only by convention), write to a uniquely-named `.part` file, `os.replace` on success, `unlink` on failure.

See `insta_dl/backends/hiker.py` for the reference implementation, and [Architecture](architecture.md) for the rationale.

## Testing your code

The test suite uses `httpx.MockTransport` to fake the CDN and a small `FakeHiker` class for the upstream API. See `tests/test_hiker_backend_http.py` and `tests/test_downloader_integration.py` for patterns. Coverage is run with `pytest --cov=insta_dl`.
