"""Immutable values at the direct X API boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re


_HANDLE = re.compile(r"[A-Za-z0-9_]{1,15}")
_ID = re.compile(r"[1-9][0-9]{5,24}")


def _utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class XPost:
    tweet_id: str
    author: str
    text: str
    created_at: datetime
    fetched_at: datetime
    post_type: str = "post"
    target_author: str = ""
    target_text: str = ""
    urls: tuple[str, ...] = ()
    bsc_contracts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        author = self.author.strip().lstrip("@").lower()
        target = self.target_author.strip().lstrip("@").lower()
        if not _ID.fullmatch(self.tweet_id) or not _HANDLE.fullmatch(author):
            raise ValueError("invalid X post identity")
        if not self.text.strip() or self.post_type not in {"post", "reply", "quote", "repost"}:
            raise ValueError("invalid X post content")
        if target and not _HANDLE.fullmatch(target):
            raise ValueError("invalid X target author")
        object.__setattr__(self, "author", author)
        object.__setattr__(self, "target_author", target)
        object.__setattr__(self, "text", self.text.strip())
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))
        object.__setattr__(self, "fetched_at", _utc(self.fetched_at, "fetched_at"))
        object.__setattr__(self, "urls", tuple(dict.fromkeys(self.urls)))
        object.__setattr__(self, "bsc_contracts", tuple(dict.fromkeys(self.bsc_contracts)))

    @property
    def canonical_url(self) -> str:
        return f"https://x.com/{self.author}/status/{self.tweet_id}"


@dataclass(frozen=True, slots=True)
class XCheckpoint:
    handle: str
    user_id: str = ""
    latest_tweet_id: str = ""

    def __post_init__(self) -> None:
        handle = self.handle.strip().lstrip("@").lower()
        if not _HANDLE.fullmatch(handle):
            raise ValueError("invalid checkpoint handle")
        if self.user_id and not _ID.fullmatch(self.user_id):
            raise ValueError("invalid checkpoint user_id")
        if self.latest_tweet_id and not _ID.fullmatch(self.latest_tweet_id):
            raise ValueError("invalid checkpoint latest_tweet_id")
        object.__setattr__(self, "handle", handle)


@dataclass(frozen=True, slots=True)
class XTimelineBatch:
    posts: tuple[XPost, ...]
    checkpoint: XCheckpoint
    fetched_items: int
    request_count: int

    def __post_init__(self) -> None:
        if self.fetched_items < 0 or self.request_count not in {1, 2}:
            raise ValueError("invalid timeline batch accounting")
        object.__setattr__(self, "posts", tuple(self.posts))


@dataclass(frozen=True, slots=True)
class XProfile:
    handle: str
    user_id: str
    display_name: str
    description: str
    fetched_at: datetime

    def __post_init__(self) -> None:
        handle = self.handle.strip().lstrip("@").lower()
        if not _HANDLE.fullmatch(handle) or not _ID.fullmatch(self.user_id):
            raise ValueError("invalid X profile identity")
        object.__setattr__(self, "handle", handle)
        object.__setattr__(self, "display_name", self.display_name.strip())
        object.__setattr__(self, "description", self.description.strip())
        object.__setattr__(self, "fetched_at", _utc(self.fetched_at, "fetched_at"))

    @property
    def canonical_url(self) -> str:
        return f"https://x.com/{self.handle}"
