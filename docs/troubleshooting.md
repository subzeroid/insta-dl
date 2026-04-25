# Troubleshooting

## Authentication

### `AuthError: HikerAPI token required`

You ran the hiker backend (default) without a token. Either:

```bash
export HIKERAPI_TOKEN='your_token'
insta-dl ...
```

or pass it inline:

```bash
insta-dl --hiker-token 'your_token' ...
```

Get a free token (100 requests, no card) at [hikerapi.com](https://hikerapi.com/p/18j4ib4j).

### HTTP 401 / 403 from HikerAPI

Token is wrong or revoked. Double-check by hitting the API directly:

```bash
curl -H "x-access-key: $HIKERAPI_TOKEN" 'https://api.hikerapi.com/v2/user/by/username?username=instagram'
```

If that fails too, regenerate the token in the dashboard.

### aiograpi: 2FA / login challenges

The aiograpi backend is still stubbed in this version. When it ships, expect:

- First run with `--login` + `--password` triggers a 2FA prompt — enter the code from your authenticator app.
- The session file written via `--session` is reused; subsequent runs skip 2FA.
- If Instagram demands a "challenge" (email/SMS code), you'll need to clear it interactively in the Instagram app first.

## Network errors

### `BackendError: refusing download from disallowed host`

A download URL points somewhere other than `*.cdninstagram.com` or `*.fbcdn.net`. This is the SSRF allowlist doing its job — almost always means the upstream API returned a malformed response. Re-run with `-v` and file an issue with the offending URL (with the signed query stripped).

### `BackendError: refusing download with disallowed scheme`

A download URL is `http://` or got redirected to one. We refuse plain-HTTP downloads on principle. Same as above — should not happen with a healthy CDN; report it.

### `BackendError: too many redirects`

A CDN URL bounced more than 10 times. Could be a transient routing issue at the CDN — retry. If it persists, file an issue.

### `BackendError: response Content-Length N exceeds max`

A single resource is bigger than 500 MB (the default cap). Bump it programmatically:

```python
HikerBackend(token="...", max_download_bytes=2 * 1024 * 1024 * 1024)  # 2 GB
```

There's no CLI flag for this yet — open an issue if you need one.

### `httpx.ConnectError` / connection reset

The hiker backend retries transport errors automatically (exponential backoff + jitter, up to 5 attempts). If you still see this, the failure is not transient — re-run and `--fast-update` will pick up from the freshest post on disk. Avoid running multiple insta-dl processes against the same `--dest` — `.part` files are uniquely named per call but parallel writers can still race on the final atomic rename.

## Rate limits

### HikerAPI 429

You've burned through your monthly quota or hit a per-minute throttle. The backend retries automatically with exponential backoff (and honors `Retry-After` when present), so transient throttles resolve themselves. If you keep hitting it after 5 attempts:

- Wait it out (per-minute caps reset within seconds).
- Check usage at the HikerAPI dashboard.
- For long-running jobs, add a `sleep` between targets in your shell loop.

### Instagram 429 (aiograpi backend)

When that backend ships, it'll inherit aiograpi's `delay_range` settings. For now, plan for "hundreds of requests per session, then back off for an hour."

## File system

### Files appear to download but `--fast-update` doesn't skip them on the next run

Check that `mtime` is being set correctly:

```bash
stat /path/to/file.mp4
```

The mtime should match the post's `taken_at`. If it shows the current time, something downstream (a backup tool, sync client, or filesystem option) is rewriting it. Disable that touch behavior or use `--latest-stamps` for cutoff tracking instead of relying on file mtimes.

### "Permission denied" writing to `--dest`

Pick a directory you own. `--dest` is a normal path — sanitization happens on the username/hashtag *components* added under it, not on `--dest` itself.

### Partial files (`*.part.uuid.part`) left behind

Should never happen on a clean exit — cleanup is in a `try/except BaseException` block. If you find one, it means the process was killed (`SIGKILL`, OOM kill) before it could clean up. Safe to delete.

## Schema drift

Instagram occasionally changes response shapes; HikerAPI patches most of these but rare ones leak through.

Symptoms:

- `[WARNING] empty URL for resource X in <code>` — a media URL field your backend expects is missing or renamed.
- `[WARNING] skipping malformed comment on <pk>` — a comment is missing a timestamp field.
- `[WARNING] post X has no owner_username; using owner_pk=Y` — the owner field is empty; falling back to numeric ID.

These are non-fatal but worth reporting via an issue with the raw API response (signed tokens stripped).

## Filenames

### Weird-looking directory: `_..something_`

That's `safe_component()` doing its job — the username/hashtag/title contained path separators or a Windows reserved name (`CON`, `NUL`) and got neutralized. Not a bug.

### Filename truncated

Components are capped at 200 chars (filesystem limits). If a profile's full name or a hashtag is enormous, it gets shortened. The `pk` / `code` is always preserved in the filename.

## Where to file an issue

[github.com/subzeroid/insta-dl/issues](https://github.com/subzeroid/insta-dl/issues). Include:

- Output of `insta-dl --version` (when versioning lands) or your `pip show insta-dl`
- Python version (`python --version`)
- The exact command you ran
- `-v` log output, with any tokens / signed URL params redacted
- Backend you used and any relevant error message
