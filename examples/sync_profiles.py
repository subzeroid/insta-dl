"""Sync a list of profiles to local disk, incrementally.

Reads usernames from a file (one per line, comments allowed),
runs them through `Downloader.download_profile` with `--fast-update`,
and persists the latest-seen `taken_at` per profile so re-runs only
touch new posts.

Usage:
    python examples/sync_profiles.py profiles.txt ./out

Where `profiles.txt`:
    instagram
    nasa
    # comments and blank lines are ignored
    natgeo
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from insta_dl.backends import make_backend
from insta_dl.downloader import Downloader, DownloadOptions
from insta_dl.latest_stamps import LatestStamps


def read_usernames(path: Path) -> list[str]:
    out: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


async def main(usernames: list[str], dest: Path) -> None:
    stamps_path = dest / ".stamps.ini"
    stamps = LatestStamps(stamps_path)
    options = DownloadOptions(
        dest=dest,
        fast_update=True,
        latest_stamps=stamps,
    )
    async with make_backend("hiker", token=os.environ["HIKERAPI_TOKEN"]) as backend:
        downloader = Downloader(backend, options)
        for username in usernames:
            try:
                await downloader.download_profile(username)
            except Exception as exc:
                print(f"!! {username}: {exc}", file=sys.stderr)
    stamps.save()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: sync_profiles.py PROFILES_FILE DEST_DIR")
    profiles_file = Path(sys.argv[1])
    dest_dir = Path(sys.argv[2])
    asyncio.run(main(read_usernames(profiles_file), dest_dir))
