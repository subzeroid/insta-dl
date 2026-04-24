from __future__ import annotations

import configparser
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class LatestStamps:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._cp = configparser.ConfigParser()
        if path.exists():
            self._cp.read(path)

    def get_post_timestamp(self, profile: str) -> datetime | None:
        raw = self._cp.get(profile, "post_timestamp", fallback=None)
        return datetime.fromisoformat(raw) if raw else None

    def set_post_timestamp(self, profile: str, when: datetime) -> None:
        if profile not in self._cp:
            self._cp[profile] = {}
        self._cp[profile]["post_timestamp"] = when.astimezone(UTC).isoformat()

    def get_story_timestamp(self, profile: str) -> datetime | None:
        raw = self._cp.get(profile, "story_timestamp", fallback=None)
        return datetime.fromisoformat(raw) if raw else None

    def set_story_timestamp(self, profile: str, when: datetime) -> None:
        if profile not in self._cp:
            self._cp[profile] = {}
        self._cp[profile]["story_timestamp"] = when.astimezone(UTC).isoformat()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"{self.path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with tmp.open("w") as f:
                self._cp.write(f)
            tmp.replace(self.path)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
