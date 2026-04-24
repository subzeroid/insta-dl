from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class MediaType(StrEnum):
    PHOTO = "photo"
    VIDEO = "video"
    ALBUM = "album"


@dataclass(slots=True)
class MediaResource:
    url: str
    is_video: bool
    width: int | None = None
    height: int | None = None


@dataclass(slots=True)
class Profile:
    pk: str
    username: str
    full_name: str | None = None
    is_private: bool = False
    is_verified: bool = False
    media_count: int | None = None
    follower_count: int | None = None
    following_count: int | None = None
    biography: str | None = None
    profile_pic_url: str | None = None


@dataclass(slots=True)
class Post:
    pk: str
    code: str
    media_type: MediaType
    taken_at: datetime
    owner_pk: str
    owner_username: str
    caption: str | None = None
    like_count: int | None = None
    comment_count: int | None = None
    resources: list[MediaResource] = field(default_factory=list)
    location_name: str | None = None
    location_lat: float | None = None
    location_lng: float | None = None


@dataclass(slots=True)
class StoryItem:
    pk: str
    taken_at: datetime
    media_type: MediaType
    owner_pk: str
    owner_username: str
    expiring_at: datetime | None = None
    resources: list[MediaResource] = field(default_factory=list)


@dataclass(slots=True)
class Highlight:
    pk: str
    title: str
    owner_pk: str
    cover_url: str | None = None


@dataclass(slots=True)
class Comment:
    pk: str
    text: str
    created_at: datetime
    user_pk: str
    user_username: str
    like_count: int | None = None
    parent_pk: str | None = None
