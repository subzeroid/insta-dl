# insta-dl

[![PyPI](https://img.shields.io/pypi/v/instagram-dl.svg)](https://pypi.org/project/instagram-dl/)
[![Python](https://img.shields.io/pypi/pyversions/instagram-dl.svg)](https://pypi.org/project/instagram-dl/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://github.com/subzeroid/insta-dl/actions/workflows/tests.yml/badge.svg)](https://github.com/subzeroid/insta-dl/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/subzeroid/insta-dl/branch/main/graph/badge.svg)](https://codecov.io/gh/subzeroid/insta-dl)
[![Docs](https://img.shields.io/badge/docs-subzeroid.github.io-blue)](https://subzeroid.github.io/insta-dl/)

Async command-line downloader for Instagram. Profiles, posts, reels, stories, highlights, hashtags, and comments — saved to disk with the original timestamps preserved.

![demo](docs/demo.gif)

```bash
pip install instagram-dl           # pip
pipx install instagram-dl          # or as an isolated CLI app

export HIKERAPI_TOKEN=your_token
insta-dl instagram
```

Or run it without installing Python at all:

```bash
docker run --rm -v "$PWD/out:/data" -e HIKERAPI_TOKEN \
    ghcr.io/subzeroid/insta-dl:latest instagram
```

Grab a free HikerAPI token at [hikerapi.com](https://hikerapi.com/p/18j4ib4j) — **first 100 requests are free**, no credit card. One request ≈ one post or one page of a feed.

**insta-dl**

- downloads **profiles, hashtags, single posts, reels, stories, highlights, and comments**,
- preserves the **original `taken_at` timestamp** as file mtime so Photos/Finder sort correctly,
- writes a **JSON metadata sidecar** next to every post (caption, like count, location, owner),
- supports **incremental updates** with `--fast-update` and `--latest-stamps`,
- accepts profile names, `#hashtag`, post shortcodes, and full `instagram.com` URLs,
- ships **two pluggable backends**: a paid commercial API (HikerAPI, no Instagram session, no ban risk) out of the box, and an opt-in private-API library via `pip install 'instagram-dl[aiograpi]'` (your own login).

```text
insta-dl [--backend hiker|aiograpi]
         [--dest DIR] [--fast-update] [--latest-stamps FILE]
         [--stories] [--highlights] [--comments]
         profile | "#hashtag" | post:SHORTCODE | https://instagram.com/...
```

📖 **[Full documentation](https://subzeroid.github.io/insta-dl/)** — installation, CLI reference, backends comparison, Python API, troubleshooting.

## How insta-dl compares to other Instagram downloaders

| | insta-dl | [instaloader](https://github.com/instaloader/instaloader) | [gallery-dl](https://github.com/mikf/gallery-dl) |
|---|---|---|---|
| Backend | [HikerAPI](https://hikerapi.com/p/18j4ib4j) cloud (default), aiograpi optional | Logged-in Instagram session | Logged-in Instagram session |
| Account ban risk | **None** with HikerAPI backend | High — your account scrapes | High — your account scrapes |
| Login required | No (HikerAPI token only) | Yes | Yes |
| Stories / highlights | ✅ | ✅ (login required) | ✅ (login required) |
| Hashtags | ✅ | ✅ (rate-limited) | ✅ (rate-limited) |
| Comments | ✅ | ✅ | ✅ |
| Async / concurrent | ✅ native asyncio | Sync | Sync |
| `taken_at` mtime | ✅ | ✅ | ⚠️ partial |
| JSON sidecar | ✅ | ✅ | ✅ |
| Multi-site (TikTok, Twitter, …) | Instagram-only | Instagram-only | ✅ 300+ sites |

**When to pick insta-dl** — you want an Instagram archive without losing your account. The default HikerAPI backend uses no Instagram session, so there's nothing for Instagram to flag, ban, or 2FA-challenge. instaloader and gallery-dl both drive scraping through your own logged-in cookies, which works until Instagram raises the rate-limit floor again.

**When to pick instaloader** — you don't want any external service in the loop and you have a throwaway Instagram account you don't mind burning. Battle-tested, huge user base, more granular `--filter` expression language.

**When to pick gallery-dl** — you want one tool for many platforms (Twitter, TikTok, DeviantArt, etc.) and Instagram is just one of them. Less Instagram-specialised but covers a much wider catalogue.

Related projects: [instaloot](https://github.com/yoryan/instaloot) (Python, less maintained), [instagram-php-scraper](https://github.com/postaddictme/instagram-php-scraper) (PHP, login-based), [aiograpi](https://github.com/subzeroid/aiograpi) (the async Instagram private API library that powers the optional `[aiograpi]` backend here).

## How to download an Instagram profile

```bash
export HIKERAPI_TOKEN=$(cat ~/.config/hikerapi-token)
insta-dl --dest ./out instagram
```

This grabs every post, names files `2026-04-21_16-04-15_DXZlTiKEpxw.mp4`, and writes a metadata sidecar next to each.

## How to keep a local archive in sync

```bash
insta-dl --fast-update --latest-stamps ./stamps.ini --dest ./out instagram
```

`--fast-update` stops at the first post that's already on disk; `--latest-stamps` records the newest `taken_at` per profile so even a deleted local copy can be resumed.

## How to download a single post or reel

```bash
insta-dl post:DXZlTiKEpxw
insta-dl https://www.instagram.com/p/DXZlTiKEpxw/
insta-dl https://www.instagram.com/reel/DXZlTiKEpxw/
```

## How to download a hashtag

```bash
insta-dl '#sunset' --dest ./out
```

Pulls the recent feed for the tag into `./out/#sunset/`.

## How to grab stories and highlights

```bash
insta-dl --stories --highlights --dest ./out instagram
```

Stories and highlights land under `<dest>/<username>/stories/` and `<dest>/<username>/highlights/<id>_<title>/`.

## How to save comments alongside posts

```bash
insta-dl --comments --dest ./out instagram
```

Each post gets a `..._comments.json` sidecar streamed to disk.

## Backends

Pick the one that matches how you want to authenticate.

| | **hiker** (default) | **aiograpi** |
|---|---|---|
| Auth | API token | Instagram login + 2FA |
| Cost | Paid per request, [**100 free requests**](https://hikerapi.com/p/18j4ib4j) to start | Free |
| Account ban risk | None — no Instagram session involved | Real, mitigated by session reuse |
| Stability vs. Instagram changes | High (managed proxy) | Brittle |
| Private profiles | What HikerAPI exposes | Anything your account can see |

Switch with `--backend`:

```bash
insta-dl --backend hiker --hiker-token TOKEN instagram
pip install 'instagram-dl[aiograpi]'   # aiograpi's deps are opt-in
insta-dl --backend aiograpi --login USER --password PASS --session ./session.json instagram
```

Detailed comparison and auth setup: see the [backends documentation](https://subzeroid.github.io/insta-dl/backends/). For how insta-dl stacks up against instaloader, yt-dlp, and gallery-dl, see [compared to alternatives](https://subzeroid.github.io/insta-dl/comparison/).

## Output layout

```
<dest>/<username>/
    2026-04-21_16-04-15_DXZlTiKEpxw.mp4
    2026-04-21_16-04-15_DXZlTiKEpxw.json           # metadata sidecar
    2026-04-21_16-04-15_DXZlTiKEpxw_comments.json  # with --comments
    stories/
        2026-04-21_18-30-00_178290.jpg             # with --stories
    highlights/
        17991_Travel/                              # with --highlights
            2025-10-12_19-20-30_4011.jpg
```

Hashtag downloads land under `<dest>/#<tag>/`; single-post downloads use the post owner's username (or `owner_pk` fallback).

## Status

This is **alpha**. Both backends (hiker, aiograpi) are functional end-to-end (278 tests, 96% coverage). aiograpi ships behind the `[aiograpi]` extra so its Rust deps don't bloat default installs. CLI flags and output layout are stable; Python API may still shift.

What's not yet implemented:

- `:feed` and `:saved` targets (account-bound, would need session reuse from aiograpi backend)

See the [changelog](CHANGELOG.md) for what landed when, and [contributing](CONTRIBUTING.md) for how to help.

## Contributing

Bug reports, fixes, and backend implementations welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md). Tests: `pip install -e .[dev] && pytest`.

## Disclaimer

insta-dl is not affiliated with, authorized, maintained, or endorsed by Instagram or Meta. Use at your own risk and respect the rights of content creators. Licensed under [MIT](LICENSE).
