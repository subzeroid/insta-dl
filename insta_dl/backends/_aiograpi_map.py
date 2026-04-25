"""Pydantic-typed aiograpi models → insta-dl DTO mappers.

aiograpi already parses raw Instagram dicts into Pydantic models with
typed fields, so these mappers are mostly attribute-access shims. The
pattern mirrors `_hiker_map.py` but is simpler — no dict.get defaults,
no ISO-string-vs-epoch dance, no shape unwrapping.
"""

from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING, Any

from ..models import Comment, Highlight, MediaResource, MediaType, Post, Profile, StoryItem

if TYPE_CHECKING:
    from datetime import datetime

# Instagram media_type codes
_PHOTO = 1
_VIDEO = 2
_ALBUM = 8


def _media_type(code: int | None) -> MediaType:
    if code == _VIDEO:
        return MediaType.VIDEO
    if code == _ALBUM:
        return MediaType.ALBUM
    return MediaType.PHOTO


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _str_url(url: Any) -> str:
    return str(url) if url is not None else ""


def _resource_from(node: Any) -> MediaResource:
    is_video = node.media_type == _VIDEO or bool(getattr(node, "video_url", None))
    if is_video:
        url = _str_url(getattr(node, "video_url", None))
    else:
        url = _str_url(getattr(node, "thumbnail_url", None))
    return MediaResource(url=url, is_video=is_video)


def map_profile(u: Any) -> Profile:
    return Profile(
        pk=str(u.pk),
        username=u.username,
        full_name=getattr(u, "full_name", None),
        is_private=bool(getattr(u, "is_private", False)),
        is_verified=bool(getattr(u, "is_verified", False)),
        media_count=getattr(u, "media_count", None),
        follower_count=getattr(u, "follower_count", None),
        following_count=getattr(u, "following_count", None),
        biography=getattr(u, "biography", None),
        profile_pic_url=_str_url(getattr(u, "profile_pic_url", None)) or None,
    )


def map_post(m: Any) -> Post:
    media_type = _media_type(m.media_type)
    user = m.user
    location = getattr(m, "location", None)

    if media_type is MediaType.ALBUM and m.resources:
        resources = [_resource_from(r) for r in m.resources]
    else:
        resources = [_resource_from(m)]

    return Post(
        pk=str(m.pk),
        code=m.code,
        media_type=media_type,
        taken_at=_utc(m.taken_at),
        owner_pk=str(user.pk),
        owner_username=user.username,
        caption=getattr(m, "caption_text", None) or None,
        like_count=getattr(m, "like_count", None),
        comment_count=getattr(m, "comment_count", None),
        resources=resources,
        location_name=location.name if location else None,
        location_lat=getattr(location, "lat", None) if location else None,
        location_lng=getattr(location, "lng", None) if location else None,
    )


def map_story(s: Any) -> StoryItem:
    user = s.user
    return StoryItem(
        pk=str(s.pk),
        taken_at=_utc(s.taken_at),
        media_type=_media_type(s.media_type),
        owner_pk=str(user.pk),
        owner_username=user.username,
        resources=[_resource_from(s)],
    )


def map_highlight(h: Any) -> Highlight:
    user = h.user
    cover_media = getattr(h, "cover_media", None)
    cover_url = None
    if cover_media is not None:
        cropped = getattr(cover_media, "cropped_image_version", None)
        if cropped is not None:
            cover_url = _str_url(getattr(cropped, "url", None)) or None
    return Highlight(
        pk=str(h.pk).removeprefix("highlight:"),
        title=h.title,
        owner_pk=str(user.pk),
        cover_url=cover_url,
    )


def map_comment(c: Any) -> Comment:
    user = c.user
    return Comment(
        pk=str(c.pk),
        text=c.text,
        created_at=_utc(c.created_at_utc),
        user_pk=str(user.pk),
        user_username=user.username,
        like_count=getattr(c, "like_count", None),
        parent_pk=getattr(c, "replied_to_comment_id", None),
    )
