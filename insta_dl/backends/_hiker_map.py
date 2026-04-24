from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..models import Comment, Highlight, MediaResource, MediaType, Post, Profile, StoryItem

# Instagram media_type codes
_PHOTO = 1
_VIDEO = 2
_ALBUM = 8


def _ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(int(value), tz=UTC)
    if isinstance(value, str):
        try:
            return datetime.fromtimestamp(int(value), tz=UTC)
        except (TypeError, ValueError):
            return datetime.fromisoformat(value)
    raise ValueError(f"can't parse timestamp from {value!r}")


def _str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _media_type(raw: Any) -> MediaType:
    code = int(raw) if raw is not None else _PHOTO
    if code == _VIDEO:
        return MediaType.VIDEO
    if code == _ALBUM:
        return MediaType.ALBUM
    return MediaType.PHOTO


def _resource_from_node(node: dict) -> MediaResource:
    is_video = bool(node.get("video_url")) or int(node.get("media_type") or 0) == _VIDEO
    if is_video:
        url = node.get("video_url") or _best_video_url(node)
    else:
        url = node.get("thumbnail_url") or _best_image_url(node)
    return MediaResource(
        url=url or "",
        is_video=is_video,
        width=node.get("original_width") or node.get("width"),
        height=node.get("original_height") or node.get("height"),
    )


def _best_image_url(node: dict) -> str | None:
    iv2 = node.get("image_versions2") or {}
    candidates = iv2.get("candidates") or []
    if candidates:
        return candidates[0].get("url")
    return None


def _best_video_url(node: dict) -> str | None:
    versions = node.get("video_versions") or []
    if versions:
        return versions[0].get("url")
    return None


def map_profile(raw: dict) -> Profile:
    return Profile(
        pk=str(raw["pk"]),
        username=raw["username"],
        full_name=raw.get("full_name"),
        is_private=bool(raw.get("is_private", False)),
        is_verified=bool(raw.get("is_verified", False)),
        media_count=raw.get("media_count"),
        follower_count=raw.get("follower_count"),
        following_count=raw.get("following_count"),
        biography=raw.get("biography"),
        profile_pic_url=raw.get("profile_pic_url"),
    )


def map_post(raw: dict) -> Post:
    media_type = _media_type(raw.get("media_type"))
    user = raw.get("user") or {}
    location = raw.get("location") or {}
    caption_text = raw.get("caption_text")
    if not caption_text and isinstance(raw.get("caption"), dict):
        caption_text = raw["caption"].get("text")

    if media_type is MediaType.ALBUM:
        nodes = raw.get("carousel_media") or raw.get("resources") or []
        resources = [_resource_from_node(n) for n in nodes]
    else:
        resources = [_resource_from_node(raw)]

    return Post(
        pk=str(raw["pk"]),
        code=raw.get("code") or raw.get("shortcode") or "",
        media_type=media_type,
        taken_at=_ts(raw.get("taken_at")),
        owner_pk=str(user.get("pk") or raw.get("user_id") or ""),
        owner_username=user.get("username") or "",
        caption=caption_text,
        like_count=raw.get("like_count"),
        comment_count=raw.get("comment_count"),
        resources=resources,
        location_name=location.get("name") if location else None,
        location_lat=location.get("lat") if location else None,
        location_lng=location.get("lng") if location else None,
    )


def map_story(raw: dict) -> StoryItem:
    user = raw.get("user") or {}
    media_type = _media_type(raw.get("media_type"))
    return StoryItem(
        pk=str(raw["pk"]),
        taken_at=_ts(raw.get("taken_at")),
        media_type=media_type,
        owner_pk=str(user.get("pk") or raw.get("user_id") or ""),
        owner_username=user.get("username") or "",
        expiring_at=_ts(raw["expiring_at"]) if raw.get("expiring_at") else None,
        resources=[_resource_from_node(raw)],
    )


def map_highlight(raw: dict) -> Highlight:
    user = raw.get("user") or {}
    cover = raw.get("cover_media") or {}
    cover_url = None
    if isinstance(cover, dict):
        cropped = cover.get("cropped_image_version") or {}
        cover_url = cropped.get("url") or cover.get("thumbnail_url")
    return Highlight(
        pk=str(raw["pk"]).removeprefix("highlight:"),
        title=raw.get("title") or "",
        owner_pk=str(user.get("pk") or ""),
        cover_url=cover_url,
    )


def map_comment(raw: dict) -> Comment:
    user = raw.get("user") or {}
    created = raw.get("created_at") or raw.get("created_at_utc")
    if created is None:
        raise ValueError(f"comment {raw.get('pk')!r} has no created_at field")
    return Comment(
        pk=str(raw["pk"]),
        text=raw.get("text") or "",
        created_at=_ts(created),
        user_pk=str(user.get("pk") or ""),
        user_username=user.get("username") or "",
        like_count=raw.get("comment_like_count") or raw.get("like_count"),
        parent_pk=_str(raw.get("parent_comment_id")),
    )
