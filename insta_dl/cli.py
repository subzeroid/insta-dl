# PYTHON_ARGCOMPLETE_OK
from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from . import __version__

if TYPE_CHECKING:
    from .downloader import Downloader

_URL_RE = re.compile(r"^https?://(?:www\.)?instagram\.com(/.*)$", re.IGNORECASE)
_URL_POST_RE = re.compile(r"^/(?:p|reel|tv)/([A-Za-z0-9_-]+)/?$")
_URL_STORIES_RE = re.compile(r"^/stories/")
_URL_PROFILE_RE = re.compile(r"^/([A-Za-z0-9_.]+)/?$")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="insta-dl",
        description="Instagram downloader with pluggable backends (hiker, aiograpi)",
    )
    p.add_argument(
        "targets",
        nargs="+",
        help="Targets: username, #hashtag, post:SHORTCODE, info:USERNAME, or instagram.com URL",
    )
    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    verbosity = p.add_mutually_exclusive_group()
    verbosity.add_argument("-v", "--verbose", action="store_true", help="DEBUG-level logging")
    verbosity.add_argument("-q", "--quiet", action="store_true", help="warnings and errors only")
    p.add_argument("--backend", choices=["hiker", "aiograpi"], default="hiker")
    p.add_argument("--dest", type=Path, default=Path())
    p.add_argument("--hiker-token", default=None, help="HikerAPI token (or HIKERAPI_TOKEN env)")
    p.add_argument("--login", default=None, help="Instagram username (aiograpi)")
    p.add_argument("--password", default=None, help="Instagram password (aiograpi)")
    p.add_argument("--session", type=Path, default=None, help="Session file (aiograpi)")
    p.add_argument("--fast-update", action="store_true")
    p.add_argument("--latest-stamps", type=Path, default=None)
    p.add_argument("--comments", action="store_true")
    p.add_argument(
        "--comments-jsonl",
        action="store_true",
        help="write comments as newline-delimited JSON (.jsonl) instead of a JSON array",
    )
    p.add_argument("--stories", action="store_true")
    p.add_argument("--highlights", action="store_true")
    p.add_argument(
        "--post-filter",
        default=None,
        metavar="EXPR",
        help=(
            "predicate expression; names: likes, comments, caption, code, username, "
            "location, taken_at, year, month, day, is_video, is_photo, is_album. "
            "Example: --post-filter 'likes > 100 and is_video'"
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="log what would be downloaded without writing to disk or hitting the CDN",
    )
    p.add_argument(
        "--no-progress",
        action="store_true",
        help="suppress the per-download progress bar (also auto-suppressed on non-TTY)",
    )
    p.add_argument(
        "--max-bytes",
        type=int,
        default=None,
        metavar="N",
        help="max bytes per downloaded resource (default: 500 MB); oversized downloads are rejected",
    )
    try:
        import argcomplete

        argcomplete.autocomplete(p)
    except ImportError:
        pass
    return p


async def _dispatch(downloader: Downloader, target: str) -> None:
    if target.startswith("#"):
        await downloader.download_hashtag(target[1:])
        return
    if target.startswith("post:"):
        await downloader.download_post(target[len("post:"):])
        return
    if target.startswith("info:"):
        import json as _json
        from dataclasses import asdict

        profile = await downloader.backend.get_profile(target[len("info:"):])
        sys.stdout.write(_json.dumps(asdict(profile), ensure_ascii=False, indent=2) + "\n")
        return
    if target.startswith(("http://", "https://")):
        url_match = _URL_RE.match(target.split("?", 1)[0].split("#", 1)[0])
        if not url_match:
            raise SystemExit(f"not an instagram.com URL: {target}")
        path = url_match.group(1)
        m = _URL_POST_RE.match(path)
        if m:
            await downloader.download_post(m.group(1))
            return
        if _URL_STORIES_RE.match(path):
            raise SystemExit("stories-by-URL not supported; use: insta-dl --stories <username>")
        m = _URL_PROFILE_RE.match(path)
        if m:
            await downloader.download_profile(m.group(1))
            return
        raise SystemExit(f"unrecognized instagram URL path: {path}")
    await downloader.download_profile(target)


async def _run(args: argparse.Namespace) -> int:
    from .backends import make_backend
    from .downloader import Downloader, DownloadOptions
    from .filter_expr import FilterExprError, compile_filter
    from .latest_stamps import LatestStamps

    backend_kwargs: dict[str, object] = {}
    if args.backend == "hiker":
        backend_kwargs["token"] = args.hiker_token
    else:
        backend_kwargs["login"] = args.login
        backend_kwargs["password"] = args.password
        backend_kwargs["session_path"] = args.session

    predicate = None
    if args.post_filter:
        try:
            predicate = compile_filter(args.post_filter)
        except FilterExprError as exc:
            sys.stderr.write(f"error: invalid --post-filter: {exc}\n")
            return 2

    stamps = LatestStamps(args.latest_stamps) if args.latest_stamps else None
    options = DownloadOptions(
        dest=args.dest,
        fast_update=args.fast_update,
        save_comments=args.comments or args.comments_jsonl,
        comments_jsonl=args.comments_jsonl,
        include_stories=args.stories,
        include_highlights=args.highlights,
        post_filter=predicate,
        latest_stamps=stamps,
        dry_run=args.dry_run,
    )
    if args.backend == "hiker":
        backend_kwargs["show_progress"] = not (args.no_progress or args.quiet)
        if args.max_bytes is not None:
            backend_kwargs["max_download_bytes"] = args.max_bytes

    async with make_backend(args.backend, **backend_kwargs) as backend:
        downloader = Downloader(backend, options)
        for target in args.targets:
            await _dispatch(downloader, target)

    if stamps is not None:
        stamps.save()
    return 0


def main() -> int:
    args = build_parser().parse_args()
    if args.verbose:
        level = logging.DEBUG
    elif args.quiet:
        level = logging.WARNING
    else:
        level = logging.INFO
    logging.basicConfig(level=level, format="%(message)s")
    from .exceptions import InstaDlError

    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 130
    except InstaDlError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
