# Backends

insta-dl talks to Instagram through a swappable backend. Pick the one that matches how you want to authenticate and what you're willing to pay (in dollars or in account-ban risk).

## At a glance

| | **hiker** *(default)* | **aiograpi** *(in development)* |
|---|---|---|
| What it is | Client for the [HikerAPI](https://hikerapi.com/p/18j4ib4j) commercial proxy | Async fork of [instagrapi](https://github.com/subzeroid/instagrapi) (private API) |
| Authentication | API token (`x-access-key` header) | Instagram username + password + 2FA |
| Cost | Paid per request, [**100 free requests**](https://hikerapi.com/p/18j4ib4j) to start | Free |
| Account-ban risk | None — your Instagram account is never used | Real, mitigated by session reuse |
| Stability when Instagram changes APIs | High — managed proxy patches things upstream | Brittle — needs library updates |
| Private profiles | Whatever HikerAPI exposes | Anything your account can already see |
| `:feed`, `:saved`, DMs | Not exposed | Available (when implemented) |
| Setup time | 30 seconds | Few minutes (login, possibly 2FA, store session) |
| Status in insta-dl | Functional | Stubbed pending an upstream sync |

## When to pick which

**Use hiker if:**

- You're building an automated archiver and don't want your Instagram account to get banned.
- You want it to *just work* and don't mind paying for stable APIs.
- You only need public data (profiles, posts, hashtags, public stories/highlights) — which is what most people need.
- You don't have an Instagram account, or don't want to use yours.

**Use aiograpi if:**

- You need to download content only your logged-in account can see (private profiles you follow, your own feed, your saved collection, DMs).
- You want zero ongoing cost and can tolerate occasional breakage when Instagram changes things.
- You're comfortable storing an Instagram session file locally.

## hiker — setup

```bash
# 1. Get a token at https://hikerapi.com (100 free requests, no card)
export HIKERAPI_TOKEN='your_token_here'

# 2. Run
insta-dl instagram
```

You can also pass the token per-invocation: `insta-dl --hiker-token 'TOKEN' instagram`.

The hiker backend talks to `https://api.hikerapi.com` for metadata and to Instagram's CDN (`*.cdninstagram.com`, `*.fbcdn.net`) for media files. Downloads are HTTPS-only (HTTP redirects are rejected), capped at 500 MB per resource, and signed query tokens are stripped before metadata is written to disk.

## hiker — what's exposed

| Capability | HikerAPI endpoint | insta-dl method |
|---|---|---|
| Profile by username | `/v2/user/by/username` | `get_profile()` |
| Single post by shortcode | `/v2/media/info/by/code` | `get_post_by_shortcode()` |
| User posts (paginated) | `/v1/user/medias/chunk` | `iter_user_posts()` |
| User stories | `/v2/user/stories` | `iter_user_stories()` |
| User highlights | `/v2/user/highlights` | `iter_user_highlights()` |
| Highlight items | `/v2/highlight/by/id` | `iter_highlight_items()` |
| Hashtag (recent) | `/v2/hashtag/medias/recent` | `iter_hashtag_posts()` |
| Post comments (paginated) | `/v2/media/comments` | `iter_post_comments()` |

## aiograpi — setup *(in development)*

```bash
insta-dl --backend aiograpi \
    --login YOUR_USERNAME \
    --password YOUR_PASSWORD \
    --session ~/.config/insta-dl/session.json \
    instagram
```

The session file is created on the first successful login and reused after that, so subsequent runs don't need the password (or trigger 2FA prompts).

For 2FA, an interactive TOTP prompt will appear during the first login. The aiograpi library supports `client.totp_seed` for non-interactive flows; insta-dl will expose this as an env variable once the backend ships.

## Adding a third backend

Both backends implement the same `InstagramBackend` ABC (see [Python API](python-api.md) and [Architecture](architecture.md)). To add a third:

1. Create `insta_dl/backends/<name>.py` with a class implementing every abstract method.
2. Map raw responses to DTOs in `insta_dl/backends/_<name>_map.py`.
3. Wire it up in `insta_dl/backends/__init__.py:make_backend`.
4. Add a `--backend <name>` choice in `insta_dl/cli.py`.

See [CONTRIBUTING.md](https://github.com/subzeroid/insta-dl/blob/main/CONTRIBUTING.md) for the checklist (host allowlist, .part safety, byte budget, tests).
