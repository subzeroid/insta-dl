# Security Policy

## Supported versions

insta-dl is pre-1.0. Only the latest published release receives security fixes.

| Version | Supported          |
| ------- | ------------------ |
| 0.0.x   | :white_check_mark: |

## Reporting a vulnerability

Please **do not** open a public issue for security-sensitive reports. Instead:

1. Use GitHub's [private vulnerability reporting](https://github.com/subzeroid/insta-dl/security/advisories/new) on this repository, **or**
2. Email the maintainer directly (see the GitHub profile linked from `pyproject.toml` `authors`).

Include:

- a description of the issue and the impact you observed,
- a minimal reproduction (inputs, commands, expected vs. actual behavior),
- the `insta-dl` version (`insta-dl --version` or the installed dist) and Python version.

You can expect:

- an acknowledgement within **7 days**,
- a fix or public advisory coordinated within **30 days** for confirmed issues,
- credit in the release notes if you'd like it.

## Scope

In scope:

- path-traversal / filename-sanitization bypasses (username, hashtag, highlight title, post code) in `filestore.safe_component`,
- URL/redirect handling in `HikerBackend.download_resource` (CDN allowlist, redirect cap, size cap, `.part` file races),
- credential or token leakage through logs, saved JSON sidecars, or on-disk artifacts.

Out of scope:

- vulnerabilities in upstream dependencies (`hikerapi`, `aiograpi`, `httpx`) — please report upstream,
- Instagram's own anti-bot or account-safety behavior,
- denial-of-service from legitimately large downloads (we set a 500 MB default cap — raise an issue if you need it lower).
