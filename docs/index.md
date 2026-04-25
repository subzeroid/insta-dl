# insta-dl

Async command-line downloader for Instagram. Profiles, posts, reels, stories, highlights, hashtags, and comments — saved to disk with original timestamps preserved.

```bash
pip install instagram-dl

export HIKERAPI_TOKEN=your_token
insta-dl instagram
```

## What it does

- Downloads **profiles, hashtags, single posts, reels, stories, highlights, and comments**.
- Preserves the **original `taken_at` timestamp** as file mtime so Photos/Finder sort correctly.
- Writes a **JSON metadata sidecar** next to every post (caption, like count, location, owner).
- Supports **incremental updates** with `--fast-update` and `--latest-stamps`.
- Accepts **profile names, `#hashtag`, post shortcodes, and full `instagram.com` URLs**.
- Ships **two interchangeable backends** so you can pick how you authenticate.

## Pick a backend

| | **hiker** (default) | **aiograpi** |
|---|---|---|
| Auth | API token | Instagram login + 2FA |
| Cost | Paid per request, [**100 free requests**](https://hikerapi.com/p/18j4ib4j) to start | Free |
| Account ban risk | None | Real |
| Stability | High | Brittle |

Full breakdown on the [Backends](backends.md) page.

## Where to next

- [**Installation**](installation.md) — set up Python, install the package, get a token.
- [**Basic usage**](basic-usage.md) — common workflows: download a profile, keep an archive in sync, grab a single post.
- [**CLI reference**](cli-reference.md) — every flag, every target form.
- [**Python API**](python-api.md) — use insta-dl as a library.
- [**Troubleshooting**](troubleshooting.md) — auth errors, rate limits, schema drift.

## Status

Alpha. Both hiker and aiograpi backends are functional end-to-end (278 tests, 96% coverage).

## License & disclaimer

MIT-licensed. Not affiliated with Instagram or Meta. Use at your own risk and respect content creators.
