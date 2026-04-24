# CLI reference

## Synopsis

```text
insta-dl [-h] [-v]
         [--backend {hiker,aiograpi}]
         [--dest DEST]
         [--hiker-token HIKER_TOKEN]
         [--login LOGIN] [--password PASSWORD] [--session SESSION]
         [--fast-update]
         [--latest-stamps LATEST_STAMPS]
         [--comments]
         [--stories] [--highlights]
         [--post-filter POST_FILTER]
         targets [targets ...]
```

## Targets

Positional. One or more, mixed forms allowed.

| Form | Meaning | Example |
|---|---|---|
| `<username>` | Download all posts by a profile | `instagram` |
| `#<tag>` | Download recent posts for a hashtag (quote it!) | `'#sunset'` |
| `post:<shortcode>` | Download one post / reel by shortcode | `post:DXZlTiKEpxw` |
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
| `--comments` | Save a `<post>_comments.json` sidecar per post, streamed incrementally. |
| `--stories` | Also download the user's stories (active 24h slot). Lands in `<dest>/<username>/stories/`. |
| `--highlights` | Also download the user's saved highlights. Lands in `<dest>/<username>/highlights/<id>_<title>/`. |
| `--post-filter EXPR` | Reserved. Currently parsed and ignored with a warning. |

### Logging

| Flag | Description |
|---|---|
| `-v`, `--verbose` | DEBUG-level logging. Shows HTTP requests, redirect chains, schema-drift warnings. |

### Help

| Flag | Description |
|---|---|
| `-h`, `--help` | Print usage and exit. |

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
