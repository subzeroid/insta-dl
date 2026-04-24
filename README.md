# insta-dl

[![PyPI](https://img.shields.io/pypi/v/instagram-dl.svg)](https://pypi.org/project/instagram-dl/)
[![Python](https://img.shields.io/pypi/pyversions/instagram-dl.svg)](https://pypi.org/project/instagram-dl/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://github.com/subzeroid/insta-dl/actions/workflows/tests.yml/badge.svg)](https://github.com/subzeroid/insta-dl/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/subzeroid/insta-dl/branch/main/graph/badge.svg)](https://codecov.io/gh/subzeroid/insta-dl)
[![Docs](https://img.shields.io/badge/docs-subzeroid.github.io-blue)](https://subzeroid.github.io/insta-dl/)

Async command-line downloader for Instagram. Profiles, posts, reels, stories, highlights, hashtags, and comments — saved to disk with the original timestamps preserved.

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
- ships **two interchangeable backends**: a paid commercial API (HikerAPI, no Instagram session, no ban risk) and an open-source private-API library (aiograpi, your own login).

```text
insta-dl [--backend hiker|aiograpi]
         [--dest DIR] [--fast-update] [--latest-stamps FILE]
         [--stories] [--highlights] [--comments]
         profile | "#hashtag" | post:SHORTCODE | https://instagram.com/...
```

📖 **[Full documentation](https://subzeroid.github.io/insta-dl/)** — installation, CLI reference, backends comparison, Python API, troubleshooting.

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

| | **hiker** (default) | **aiograpi** *(in development)* |
|---|---|---|
| Auth | API token | Instagram login + 2FA |
| Cost | Paid per request, [**100 free requests**](https://hikerapi.com/p/18j4ib4j) to start | Free |
| Account ban risk | None — no Instagram session involved | Real, mitigated by session reuse |
| Stability vs. Instagram changes | High (managed proxy) | Brittle |
| Private profiles | What HikerAPI exposes | Anything your account can see |

Switch with `--backend`:

```bash
insta-dl --backend hiker --hiker-token TOKEN instagram
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

This is **alpha**. The hiker backend is functional end-to-end (197 tests, 95% coverage). The aiograpi backend is stubbed pending an upstream sync. CLI flags and output layout are stable; Python API may still shift.

What's not yet implemented:

- private profiles requiring login (waiting on aiograpi)
- `:feed` and `:saved` (account-bound, blocked on aiograpi)
- post-filter expressions (planned: AST-restricted eval)
- automatic retry/backoff on 429/5xx

See the [changelog](CHANGELOG.md) for what landed when, and [contributing](CONTRIBUTING.md) for how to help.

## Contributing

Bug reports, fixes, and backend implementations welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md). Tests: `pip install -e .[dev] && pytest`.

## Disclaimer

insta-dl is not affiliated with, authorized, maintained, or endorsed by Instagram or Meta. Use at your own risk and respect the rights of content creators. Licensed under [MIT](LICENSE).
