# Basic usage

This page walks through the common workflows. For an exhaustive flag list see the [CLI reference](cli-reference.md).

All examples assume `HIKERAPI_TOKEN` is in your environment. To use a different backend, prepend `--backend aiograpi` and the appropriate auth flags — see [Backends](backends.md).

## Download a profile

```bash
insta-dl --dest ./out instagram
```

Pulls every post by `@instagram` into `./out/instagram/`. Each media file is named `<date>_<shortcode>[_<index>].<ext>` and gets a JSON sidecar with caption, like count, location, and owner.

You can pass several profiles in one go:

```bash
insta-dl --dest ./out instagram natgeo nasa
```

## Keep a local archive in sync

The naive way: re-run the same command every day. insta-dl checks `path.exists()` before each download, so it won't re-fetch what's already on disk — but it still talks to the API for every post.

The fast way: `--fast-update` stops at the first post you already have.

```bash
insta-dl --fast-update --dest ./out instagram
```

This works as long as you keep the directory intact. If you delete files but want to remember "last seen post" cheaply, add `--latest-stamps`:

```bash
insta-dl --fast-update --latest-stamps ./stamps.ini --dest ./out instagram
```

`stamps.ini` records the newest `taken_at` per profile in a tiny INI file. Even if you wipe `./out/`, the next run with the same `--latest-stamps` will still resume from where you left off.

## Download a single post or reel

By shortcode:

```bash
insta-dl post:DXZlTiKEpxw
```

By URL (post / reel / IGTV — case-insensitive, query string and fragment ignored):

```bash
insta-dl https://www.instagram.com/p/DXZlTiKEpxw/
insta-dl https://instagram.com/reel/DXZlTiKEpxw/
insta-dl 'https://www.instagram.com/p/DXZlTiKEpxw/?igshid=...'
```

Files land under `<dest>/<owner_username>/`, just like profile downloads. If the API doesn't expose the owner's username, the post owner's numeric `pk` is used as the directory name.

## Download a hashtag

```bash
insta-dl '#sunset' --dest ./out
```

Pulls the recent feed for the tag into `./out/#sunset/`. **Quote the argument** so your shell doesn't treat `#` as a comment.

## Stories and highlights

```bash
insta-dl --stories --dest ./out instagram
insta-dl --highlights --dest ./out instagram
insta-dl --stories --highlights --dest ./out instagram
```

Stories land under `<dest>/<username>/stories/`. Highlights under `<dest>/<username>/highlights/<id>_<title>/` — the numeric ID prefix guarantees no collision when two highlights share a name.

You can also fetch them standalone (without the full profile):

```bash
insta-dl --stories instagram
insta-dl --highlights instagram
```

## Save comments

```bash
insta-dl --comments --dest ./out instagram
```

For every post, you get an additional `<date>_<shortcode>_comments.json` sidecar containing each comment's text, author, timestamp, and like count. Comments are streamed to disk incrementally — fine for posts with thousands of comments.

## Geotags

Geotag information (`location_name`, `location_lat`, `location_lng`) is already saved inside every per-post `.json` sidecar — no separate flag needed. To extract just locations from an archive:

```bash
jq '{code, location_name, location_lat, location_lng}' out/instagram/*.json
```

## Combine everything

```bash
insta-dl --fast-update --latest-stamps ./stamps.ini \
         --stories --highlights --comments \
         --dest ./out \
         instagram natgeo nasa
```

A reasonable nightly cron entry:

```cron
0 3 * * * /usr/local/bin/insta-dl --fast-update --latest-stamps /var/insta-dl/stamps.ini --dest /var/insta-dl/archive instagram natgeo
```

## Pick a backend

Default is **hiker** (HikerAPI). Switch explicitly:

```bash
insta-dl --backend hiker instagram             # explicit
insta-dl --backend aiograpi --login U --password P --session ./s.json instagram
```

The trade-offs are on the [Backends](backends.md) page.

## Verbose output

```bash
insta-dl -v --dest ./out instagram
```

Adds DEBUG-level logging — useful for diagnosing schema drift, redirect chains, and retry decisions.
