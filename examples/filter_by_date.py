"""Download only posts within a date range, scripted.

Combines the post-filter expression compiler (same one --post-filter
uses) with the Python API, so the filter logic stays AST-restricted
and can't be smuggled past the safety net.

Usage:
    HIKERAPI_TOKEN=... python examples/filter_by_date.py instagram 2026 4
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from insta_dl.backends import make_backend
from insta_dl.downloader import Downloader, DownloadOptions
from insta_dl.filter_expr import compile_filter


async def main(username: str, year: int, month: int) -> None:
    predicate = compile_filter(f"year == {year} and month == {month}")
    options = DownloadOptions(
        dest=Path(f"./out-{year}-{month:02d}"),
        post_filter=predicate,
    )
    async with make_backend("hiker", token=os.environ["HIKERAPI_TOKEN"]) as backend:
        downloader = Downloader(backend, options)
        await downloader.download_profile(username)
    print(f"done: {downloader.stats.summary()}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage: filter_by_date.py USERNAME YEAR MONTH")
    asyncio.run(main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3])))
