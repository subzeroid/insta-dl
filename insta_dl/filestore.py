from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

# C0 + C1 control chars, path separators, and Windows-forbidden chars
_UNSAFE_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f/\\:*?\"<>|]")
# Bidi/zero-width/invisible formatting chars that confuse filenames
_INVISIBLE = re.compile(r"[​-‏‪-‮⁠-⁤﻿]")
_RESERVED_LITERAL = {".", ".."}
_WIN_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_MAX_COMPONENT = 200
_ULTIMATE_FALLBACK = "untitled"


def _sanitize(raw: object) -> str:
    if not isinstance(raw, str):
        raw = str(raw)
    cleaned = _INVISIBLE.sub("", raw)
    cleaned = _UNSAFE_CHARS.sub("_", cleaned)
    # strip leading/trailing whitespace AND dots (Windows hates trailing dot/space)
    cleaned = cleaned.strip().strip(". ")
    if not cleaned or cleaned in _RESERVED_LITERAL:
        return ""
    if cleaned.upper().split(".", 1)[0] in _WIN_RESERVED:
        cleaned = "_" + cleaned
    if len(cleaned) > _MAX_COMPONENT:
        cleaned = cleaned[:_MAX_COMPONENT]
    return cleaned


def safe_component(name: object, fallback: object = _ULTIMATE_FALLBACK) -> str:
    """Sanitize a single path component from untrusted input.

    Applies the same sanitizer to `fallback`, so backends cannot smuggle
    traversal through a secondary field. If both primary and fallback
    sanitize to empty, returns the ultimate hardcoded fallback.
    """
    cleaned = _sanitize(name)
    if cleaned:
        return cleaned
    cleaned = _sanitize(fallback)
    if cleaned:
        return cleaned
    return _ULTIMATE_FALLBACK


def post_filename(shortcode: object, taken_at: datetime, index: int = 0, ext: object = "jpg") -> str:
    stamp = taken_at.strftime("%Y-%m-%d_%H-%M-%S")
    suffix = f"_{index}" if index else ""
    code = safe_component(shortcode, fallback="post")
    safe_ext = safe_component(ext, fallback="bin")
    return f"{stamp}_{code}{suffix}.{safe_ext}"


def apply_mtime(path: Path, when: datetime) -> None:
    ts = when.timestamp()
    os.utime(path, (ts, ts))


def ext_from_url(url: str, default: str = "jpg") -> str:
    tail = url.split("?", 1)[0].rsplit(".", 1)
    if len(tail) == 2 and 1 <= len(tail[1]) <= 4 and tail[1].isalnum():
        return tail[1].lower()
    return default
