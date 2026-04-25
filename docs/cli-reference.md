# CLI reference

## Synopsis

```text
insta-dl [-h] [-V] [-v]
         [--backend {hiker,aiograpi}]
         [--dest DEST]
         [--hiker-token HIKER_TOKEN]
         [--login LOGIN] [--password PASSWORD] [--session SESSION]
         [--fast-update]
         [--latest-stamps LATEST_STAMPS]
         [--comments]
         [--stories] [--highlights]
         [--post-filter EXPR]
         targets [targets ...]
```

## Targets

Positional. One or more, mixed forms allowed.

| Form | Meaning | Example |
|---|---|---|
| `<username>` | Download all posts by a profile | `instagram` |
| `#<tag>` | Download recent posts for a hashtag (quote it!) | `'#sunset'` |
| `post:<shortcode>` | Download one post / reel by shortcode | `post:DXZlTiKEpxw` |
| `info:<username>` | Print profile metadata as JSON to stdout and exit (no download) | `info:instagram` |
| `https://[www.]instagram.com/p/<code>/` | Same, by URL | `https://www.instagram.com/p/DXZlTiKEpxw/` |
| `https://[www.]instagram.com/reel/<code>/` | Same, for reels | `https://instagram.com/reel/DXZlTiKEpxw/` |
| `https://[www.]instagram.com/tv/<code>/` | Same, for IGTV | `https://instagram.com/tv/DXZlTiKEpxw/` |
| `https://[www.]instagram.com/<username>/` | Same as bare `<username>` | `https://instagram.com/instagram/` |

URL parsing is case-insensitive, anchored on the host (`evil.com/instagram.com/...` is rejected), and ignores `?query` and `#fragment`. Stories-by-URL (`https://instagram.com/stories/...`) is rejected with an explicit message — use `--stories <username>` instead.

## Options

### Backend selection

| Flag | Default | Description |
|---|---|---|
| `--backend {hiker,aiograpi}` | `hiker` | Which transport to use. See [Backends](backends.md). |

### hiker backend

| Flag | Source | Description |
|---|---|---|
| `--hiker-token TOKEN` | env `HIKERAPI_TOKEN` | Required. Get one at [hikerapi.com](https://hikerapi.com/p/18j4ib4j). |

### aiograpi backend *(in development)*

| Flag | Description |
|---|---|
| `--login USER` | Instagram username. |
| `--password PASS` | Instagram password. |
| `--session PATH` | Session-file path. Created on first successful login, reused after. |

### Output

| Flag | Default | Description |
|---|---|---|
| `--dest DIR` | `.` | Where files are written. Subdirectories `<dest>/<username>/`, `<dest>/#<tag>/` are created automatically. |

### Incremental updates

| Flag | Description |
|---|---|
| `--fast-update` | Stop iterating posts at the first one already on disk. Skip already-downloaded resource files (uses `.exists()` check). |
| `--latest-stamps FILE` | INI file recording the newest `taken_at` per profile. Used as a cutoff when `--fast-update` is set; updated at the end of each run. |

### Extras

| Flag | Description |
|---|---|
| `--comments` | Save a `<post>_comments.json` sidecar per post (single JSON array, streamed incrementally). |
| `--comments-jsonl` | Save comments as `<post>_comments.jsonl` (newline-delimited JSON, one object per line). Better for posts with hundreds of thousands of comments — streamable line-by-line by tools like `jq -c`. Implies `--comments`. |
| `--stories` | Also download the user's stories (active 24h slot). Lands in `<dest>/<username>/stories/`. |
| `--highlights` | Also download the user's saved highlights. Lands in `<dest>/<username>/highlights/<id>_<title>/`. |
| `--post-filter EXPR` | Restricted-AST predicate evaluated against each post; posts where the expression is falsy are skipped. See [Post filter expressions](#post-filter-expressions) below. |
| `--dry-run` | Walk the iteration as if downloading, but skip CDN fetches and sidecar writes. Logs `[dry-run] would download → <filename>` per resource. Useful for sanity-checking `--post-filter` expressions. Metadata API calls still happen because filters are evaluated against full `Post` records. |
| `--no-progress` | Suppress the per-download progress bar even on a TTY. (Non-TTY destinations like CI logs auto-suppress regardless.) |
| `--max-bytes N` | Override the 500 MB per-resource cap. Oversized downloads are still rejected before bytes hit disk. |
| `--concurrency N` | Max parallel CDN fetches across the whole run (default: `4`). Caps total in-flight downloads regardless of whether they come from one carousel post or many single-photo posts in a profile/hashtag. Higher = faster, more CDN load. |

### Logging

| Flag | Description |
|---|---|
| `-v`, `--verbose` | DEBUG-level logging. Shows HTTP requests, redirect chains, schema-drift warnings. |
| `-q`, `--quiet` | Warnings and errors only. Also suppresses the per-download progress bar. Mutually exclusive with `-v`. |

A summary line is emitted at the end of every profile / hashtag run:

```
profile instagram: downloaded 8 · filtered 12 · already on disk 4
```

Counts:
- **downloaded** — posts where at least one resource was newly written (or, with `--dry-run`, would be).
- **filtered** — posts excluded by `--post-filter`.
- **already on disk** — posts where every resource was already present and `--fast-update` skipped them.

### Help

| Flag | Description |
|---|---|
| `-h`, `--help` | Print usage and exit. |
| `-V`, `--version` | Print version and exit. |

## Post filter expressions

`--post-filter EXPR` compiles a Python-like expression once and runs it against each post; a falsy result skips the post. Only a restricted AST is accepted — no attribute access, subscription, calls, or lambdas — so misuse fails fast rather than silently pulling everything.

Names available inside the expression:

| Name | Type | Value |
|---|---|---|
| `likes` | `int` | `post.like_count` or `0` if unknown |
| `comments` | `int` | `post.comment_count` or `0` if unknown |
| `caption` | `str` | Post caption, empty string if none |
| `code` | `str` | Shortcode (e.g. `DXZlTiKEpxw`) |
| `username` | `str` | `post.owner_username` |
| `location` | `str` | Location name, empty string if none |
| `taken_at` | `datetime` | Post timestamp (use `year` / `month` / `day` for comparisons) |
| `year`, `month`, `day` | `int` | Convenience extracts of `taken_at` |
| `is_video`, `is_photo`, `is_album` | `bool` | Media-type flags |

Examples:

```bash
insta-dl --post-filter 'likes > 1000 and is_video'             instagram
insta-dl --post-filter "'sunset' in caption"                   '#photography'
insta-dl --post-filter 'year == 2026 and month >= 4'           instagram
insta-dl --post-filter "username in ('instagram', 'meta')"     '#tech'
```

## Shell completions

insta-dl is compatible with [argcomplete](https://kislyuk.github.io/argcomplete/). Enable once per shell:

```bash
# bash / zsh — one-off
eval "$(register-python-argcomplete insta-dl)"

# bash — persistent
activate-global-python-argcomplete --user

# zsh — add to ~/.zshrc
autoload -U bashcompinit && bashcompinit
eval "$(register-python-argcomplete insta-dl)"
```

After activation: `insta-dl --<TAB>` completes flag names.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `130` | Interrupted with Ctrl-C |
| Other | Uncaught exception (with traceback) — file an issue |

## Environment variables

| Variable | Used by | Description |
|---|---|---|
| `HIKERAPI_TOKEN` | hiker backend | Default token source if `--hiker-token` not given. |

## Output layout

```
<dest>/<username>/
    2026-04-21_16-04-15_DXZlTiKEpxw.mp4              # media
    2026-04-21_16-04-15_DXZlTiKEpxw.json             # metadata sidecar
    2026-04-21_16-04-15_DXZlTiKEpxw_comments.json    # with --comments
    2026-04-21_16-04-15_DXZlTiKEpxw_1.jpg            # carousel children get _1, _2, ...
    stories/
        2026-04-21_18-30-00_178290.mp4               # with --stories
    highlights/
        17991_Travel/                                # with --highlights
            2025-10-12_19-20-30_4011.jpg

<dest>/#<tag>/
    2026-04-22_10-15-00_ABCDE.jpg                    # hashtag downloads
```

File `mtime` matches the post's `taken_at`. Path components from the API (username, owner, hashtag, highlight title) are sanitized: path separators replaced, `..` and reserved Windows names neutered, bidi/zero-width characters stripped, length capped at 200.

## Sidecar JSON shape

```json
{
  "pk": "3880296624023575664",
  "code": "DXZlTiKEpxw",
  "media_type": "video",
  "taken_at": "2026-04-21T16:04:15+00:00",
  "owner_pk": "25025320",
  "owner_username": "instagram",
  "caption": "...",
  "like_count": 181649,
  "comment_count": 3517,
  "resources": [
    {
      "url": "https://scontent.cdninstagram.com/.../...mp4",
      "is_video": true,
      "width": null,
      "height": null
    }
  ],
  "location_name": null,
  "location_lat": null,
  "location_lng": null
}
```

URLs in the sidecar are stripped of query parameters — signed CDN tokens (`oh=`, `oe=`, `_nc_sid`) are not persisted to disk.
