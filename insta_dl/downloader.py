from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlsplit, urlunsplit

from .filestore import apply_mtime, ext_from_url, post_filename, safe_component

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from pathlib import Path

    from .backend import InstagramBackend
    from .latest_stamps import LatestStamps
    from .models import Post

log = logging.getLogger("insta_dl")


@dataclass(slots=True)
class DownloadOptions:
    dest: Path
    fast_update: bool = False
    save_comments: bool = False
    save_metadata: bool = True
    include_stories: bool = False
    include_highlights: bool = False
    post_filter: Callable[[Post], bool] | None = None
    latest_stamps: LatestStamps | None = None
    dry_run: bool = False


@dataclass(slots=True)
class RunStats:
    """Counts emitted at the end of every download_profile / download_hashtag."""

    new_posts: int = 0
    skipped_filter: int = 0
    skipped_existing: int = 0

    def summary(self, *, dry_run: bool = False) -> str:
        verb = "would download" if dry_run else "downloaded"
        parts = [f"{verb} {self.new_posts}"]
        if self.skipped_filter:
            parts.append(f"filtered {self.skipped_filter}")
        if self.skipped_existing:
            parts.append(f"already on disk {self.skipped_existing}")
        return " · ".join(parts)


class Downloader:
    def __init__(self, backend: InstagramBackend, options: DownloadOptions) -> None:
        self.backend = backend
        self.options = options
        self.stats = RunStats()

    def _keep(self, post: Post) -> bool:
        if self.options.post_filter is None:
            return True
        try:
            keep = self.options.post_filter(post)
        except Exception as exc:
            log.warning("post-filter raised on %s: %s — skipping", post.code, exc)
            return False
        if not keep:
            self.stats.skipped_filter += 1
        return keep

    async def download_profile(self, username: str) -> None:
        before = _snapshot(self.stats)
        profile = await self.backend.get_profile(username)
        target_dir = self.options.dest / safe_component(profile.username, fallback=profile.pk)
        target_dir.mkdir(parents=True, exist_ok=True)
        log.info("profile %s pk=%s media=%s", profile.username, profile.pk, profile.media_count)

        # Stamps are keyed by the canonical, lowercased username so `Instagram`
        # and `instagram` don't fight over different cutoff records.
        stamp_key = (profile.username or username).lower()
        cutoff = self._cutoff_for(stamp_key)
        latest_seen: datetime | None = None

        async for post in self.backend.iter_user_posts(profile.pk):
            if cutoff and post.taken_at <= cutoff:
                log.info("fast-update: reached %s, stopping", post.taken_at.isoformat())
                break
            if not self._keep(post):
                continue
            await self._save_post(post, target_dir)
            if latest_seen is None or post.taken_at > latest_seen:
                latest_seen = post.taken_at

        if latest_seen and self.options.latest_stamps is not None:
            self.options.latest_stamps.set_post_timestamp(stamp_key, latest_seen)

        if self.options.include_stories:
            await self._download_stories(profile.pk, target_dir / "stories")
        if self.options.include_highlights:
            await self._download_highlights(profile.pk, target_dir / "highlights")

        log.info("profile %s: %s", profile.username, _delta(self.stats, before).summary(dry_run=self.options.dry_run))

    async def download_post(self, shortcode: str) -> None:
        post = await self.backend.get_post_by_shortcode(shortcode)
        owner_raw = post.owner_username or post.owner_pk
        if not post.owner_username:
            log.warning("post %s has no owner_username; using owner_pk=%s", post.code, post.owner_pk)
        if not owner_raw:
            raise ValueError(f"post {post.code} has neither owner_username nor owner_pk")
        target_dir = self.options.dest / safe_component(owner_raw)
        target_dir.mkdir(parents=True, exist_ok=True)
        await self._save_post(post, target_dir)

    async def download_stories(self, username: str) -> None:
        profile = await self.backend.get_profile(username)
        user_dir = self.options.dest / safe_component(profile.username, fallback=profile.pk)
        await self._download_stories(profile.pk, user_dir / "stories")

    async def download_highlights(self, username: str) -> None:
        profile = await self.backend.get_profile(username)
        user_dir = self.options.dest / safe_component(profile.username, fallback=profile.pk)
        await self._download_highlights(profile.pk, user_dir / "highlights")

    async def download_hashtag(self, tag: str) -> None:
        before = _snapshot(self.stats)
        target_dir = self.options.dest / f"#{safe_component(tag, fallback='tag')}"
        target_dir.mkdir(parents=True, exist_ok=True)
        async for post in self.backend.iter_hashtag_posts(tag):
            if not self._keep(post):
                continue
            await self._save_post(post, target_dir)
        log.info("#%s: %s", tag, _delta(self.stats, before).summary(dry_run=self.options.dry_run))

    async def _save_post(self, post: Post, target_dir: Path) -> None:
        downloaded_any = False
        all_existed = True
        for index, resource in enumerate(post.resources):
            if not resource.url:
                log.warning("empty URL for resource %d in %s — schema drift?", index, post.code)
                continue
            ext = ext_from_url(resource.url, default="mp4" if resource.is_video else "jpg")
            name = post_filename(post.code, post.taken_at, index=index, ext=ext)
            path = target_dir / name
            if path.exists() and self.options.fast_update:
                continue
            all_existed = False
            if self.options.dry_run:
                log.info("[dry-run] would download → %s", path.name)
                downloaded_any = True
                continue
            log.info("→ %s", path.name)
            await self.backend.download_resource(resource.url, path)
            apply_mtime(path, post.taken_at)
            downloaded_any = True

        if downloaded_any:
            self.stats.new_posts += 1
        elif all_existed and post.resources:
            self.stats.skipped_existing += 1

        safe_code = safe_component(post.code, fallback="post")
        stem = f"{post.taken_at.strftime('%Y-%m-%d_%H-%M-%S')}_{safe_code}"
        if self.options.save_metadata and not self.options.dry_run:
            meta_path = target_dir / f"{stem}.json"
            tmp_meta = meta_path.with_name(f"{meta_path.name}.{uuid.uuid4().hex}.tmp")
            try:
                tmp_meta.write_text(_post_to_json(post), encoding="utf-8")
                tmp_meta.replace(meta_path)
            except BaseException:
                tmp_meta.unlink(missing_ok=True)
                raise
            apply_mtime(meta_path, post.taken_at)

        if self.options.save_comments and not self.options.dry_run:
            comments_path = target_dir / f"{stem}_comments.json"
            tmp = comments_path.with_name(f"{comments_path.name}.{uuid.uuid4().hex}.tmp")
            try:
                with tmp.open("w", encoding="utf-8") as f:
                    f.write("[")
                    first = True
                    async for c in self.backend.iter_post_comments(post.pk):
                        row = asdict(c)
                        row["created_at"] = c.created_at.isoformat()
                        if not first:
                            f.write(",")
                        f.write("\n  ")
                        f.write(json.dumps(row, ensure_ascii=False))
                        first = False
                    f.write("\n]" if not first else "]")
                tmp.replace(comments_path)
            except BaseException:
                tmp.unlink(missing_ok=True)
                raise
            apply_mtime(comments_path, post.taken_at)

    async def _download_stories(self, user_pk: str, target_dir: Path) -> None:
        target_dir.mkdir(parents=True, exist_ok=True)
        async for item in self.backend.iter_user_stories(user_pk):
            for index, res in enumerate(item.resources):
                if not res.url:
                    log.warning("empty URL for story resource %d in %s", index, item.pk)
                    continue
                ext = ext_from_url(res.url, default="mp4" if res.is_video else "jpg")
                name = post_filename(item.pk, item.taken_at, index=index, ext=ext)
                path = target_dir / name
                if path.exists() and self.options.fast_update:
                    continue
                if self.options.dry_run:
                    log.info("[dry-run] would download story → %s", path.name)
                    continue
                log.info("story → %s", path.name)
                await self.backend.download_resource(res.url, path)
                apply_mtime(path, item.taken_at)

    async def _download_highlights(self, user_pk: str, target_dir: Path) -> None:
        target_dir.mkdir(parents=True, exist_ok=True)
        async for hl in self.backend.iter_user_highlights(user_pk):
            sub = target_dir / safe_component(f"{hl.pk}_{hl.title}", fallback=hl.pk or "highlight")
            sub.mkdir(parents=True, exist_ok=True)
            async for item in self.backend.iter_highlight_items(hl.pk):
                for index, res in enumerate(item.resources):
                    if not res.url:
                        log.warning("empty URL for highlight resource %d in %s", index, item.pk)
                        continue
                    ext = ext_from_url(res.url, default="mp4" if res.is_video else "jpg")
                    path = sub / post_filename(item.pk, item.taken_at, index=index, ext=ext)
                    if path.exists() and self.options.fast_update:
                        continue
                    if self.options.dry_run:
                        log.info("[dry-run] would download highlight → %s", path.name)
                        continue
                    await self.backend.download_resource(res.url, path)
                    apply_mtime(path, item.taken_at)

    def _cutoff_for(self, username: str) -> datetime | None:
        if not self.options.fast_update or self.options.latest_stamps is None:
            return None
        return self.options.latest_stamps.get_post_timestamp(username)


def _snapshot(s: RunStats) -> RunStats:
    return RunStats(
        new_posts=s.new_posts,
        skipped_filter=s.skipped_filter,
        skipped_existing=s.skipped_existing,
    )


def _delta(now: RunStats, before: RunStats) -> RunStats:
    return RunStats(
        new_posts=now.new_posts - before.new_posts,
        skipped_filter=now.skipped_filter - before.skipped_filter,
        skipped_existing=now.skipped_existing - before.skipped_existing,
    )


def _strip_query(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _post_to_json(post: Post) -> str:
    data = asdict(post)
    data["taken_at"] = post.taken_at.isoformat()
    data["media_type"] = post.media_type.value
    for res in data.get("resources", []):
        if res.get("url"):
            res["url"] = _strip_query(res["url"])
    return json.dumps(data, ensure_ascii=False, indent=2)


