"""Pull the first N posts of a hashtag's recent feed, with comments.

Demonstrates breaking out of `iter_hashtag_posts` early without
exhausting the cursor — useful for sampling large hashtags.

Usage:
    HIKERAPI_TOKEN=... python examples/hashtag_sample.py sunset 50
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from insta_dl.backends import make_backend
from insta_dl.downloader import Downloader, DownloadOptions


async def main(tag: str, limit: int) -> None:
    options = DownloadOptions(dest=Path("./out"), save_comments=True, comments_jsonl=True)
    async with make_backend("hiker", token=os.environ["HIKERAPI_TOKEN"]) as backend:
        downloader = Downloader(backend, options)
        target_dir = options.dest / f"#{tag}"
        target_dir.mkdir(parents=True, exist_ok=True)
        seen = 0
        async for post in backend.iter_hashtag_posts(tag):
            if seen >= limit:
                break
            await downloader._save_post(post, target_dir)
            seen += 1
        print(f"sampled {seen}/{limit} posts for #{tag}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: hashtag_sample.py TAG LIMIT")
    asyncio.run(main(sys.argv[1], int(sys.argv[2])))
