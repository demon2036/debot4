"""Strict parsing for historical X profile and timeline evidence snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
from typing import Mapping

from .content import content_text
from .http import FxTwitterError


_HANDLE = re.compile(r"[A-Za-z0-9_]{1,15}")
_ID = re.compile(r"[1-9][0-9]{5,24}")
_AVATAR_ID = re.compile(r"/profile_images/([1-9][0-9]{5,24})/")
_BANNER_TIME = re.compile(r"/profile_banners/[1-9][0-9]{5,24}/([0-9]{9,12})(?:/|$)")
_SNOWFLAKE_EPOCH_MS = 1_288_834_974_657


class XForensicError(FxTwitterError):
    """A sanitized identity, timestamp, or provider-schema failure."""


@dataclass(frozen=True, slots=True)
class XForensicProfile:
    handle: str
    user_id: str
    display_name: str
    description: str
    joined_at: datetime
    avatar_url: str
    avatar_resource_id: str | None
    avatar_resource_at: datetime | None
    banner_url: str
    banner_resource_at: datetime | None
    verified: bool
    verification_type: str | None
    followers: int | None
    tweets: int | None
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class XForensicAction:
    timeline_actor: str
    timeline_actor_id: str
    action_kind: str
    tweet_id: str
    original_author: str
    original_author_id: str
    text: str
    original_status_created_at: datetime
    exact_action_time_available: bool
    target_author: str
    target_text: str
    media_ids: tuple[str, ...]
    media_urls: tuple[str, ...]
    likes_observed: int | None
    reposts_observed: int | None
    replies_observed: int | None
    views_observed: int | None
    fetched_at: datetime

    @property
    def canonical_url(self) -> str:
        return f"https://x.com/{self.original_author}/status/{self.tweet_id}"


@dataclass(frozen=True, slots=True)
class XForensicTimelinePage:
    actions: tuple[XForensicAction, ...]
    bottom_cursor: str
    result_count: int


def parse_forensic_profile(
    payload: object,
    *,
    expected_handle: str,
    expected_user_id: str,
    fetched_at: datetime,
) -> XForensicProfile:
    """Parse a current profile while pinning both handle and stable user ID."""

    if not isinstance(payload, Mapping) or payload.get("code") != 200:
        raise XForensicError("FxTwitter forensic profile schema is invalid")
    user = payload.get("user")
    if not isinstance(user, Mapping):
        raise XForensicError("FxTwitter forensic profile schema is invalid")
    handle, user_id = _identity(user, "profile")
    expected = _handle(expected_handle)
    if handle != expected or user_id != expected_user_id:
        raise XForensicError("FxTwitter forensic profile identity mismatch")
    avatar_url = str(user.get("avatar_url") or "").strip()
    banner_url = str(user.get("banner_url") or "").strip()
    avatar_id, avatar_at = _avatar_resource(avatar_url)
    verification = user.get("verification")
    verification = verification if isinstance(verification, Mapping) else {}
    return XForensicProfile(
        handle=handle,
        user_id=user_id,
        display_name=str(user.get("name") or "").strip(),
        description=str(user.get("description") or "").strip(),
        joined_at=_twitter_time(user.get("joined"), "profile joined"),
        avatar_url=avatar_url,
        avatar_resource_id=avatar_id,
        avatar_resource_at=avatar_at,
        banner_url=banner_url,
        banner_resource_at=_banner_resource(banner_url),
        verified=verification.get("verified") is True,
        verification_type=(
            str(verification.get("type")) if verification.get("type") else None
        ),
        followers=_count(user.get("followers")),
        tweets=_count(user.get("tweets")),
        fetched_at=_utc(fetched_at, "profile fetched_at"),
    )


def parse_forensic_timeline_page(
    payload: object,
    *,
    expected_handle: str,
    expected_user_id: str,
    fetched_at: datetime,
) -> XForensicTimelinePage:
    """Preserve direct posts and repost membership without forging repost time."""

    if not isinstance(payload, Mapping) or payload.get("code") != 200:
        raise XForensicError("FxTwitter forensic timeline schema is invalid")
    rows = payload.get("results")
    if not isinstance(rows, list) or len(rows) > 100:
        raise XForensicError("FxTwitter forensic timeline schema is invalid")
    expected = _handle(expected_handle)
    actions = []
    for row in rows:
        if not isinstance(row, Mapping) or row.get("type") != "status":
            continue
        actions.append(_action(row, expected, expected_user_id, fetched_at))
    cursor = payload.get("cursor")
    bottom = str(cursor.get("bottom") or "") if isinstance(cursor, Mapping) else ""
    if len(bottom) > 4_096:
        raise XForensicError("FxTwitter forensic cursor is invalid")
    return XForensicTimelinePage(tuple(actions), bottom, len(rows))


def _action(
    row: Mapping[str, object], expected: str, expected_id: str, fetched_at: datetime,
) -> XForensicAction:
    repost = row.get("reposted_by")
    actor, actor_id = _identity(repost or row.get("author"), "timeline actor")
    if actor != expected or actor_id != expected_id:
        raise XForensicError("FxTwitter forensic timeline identity mismatch")
    original, original_id = _identity(row.get("author"), "original author")
    tweet_id = str(row.get("id") or "").strip()
    if not _ID.fullmatch(tweet_id):
        raise XForensicError("FxTwitter forensic status identity is invalid")
    quote = row.get("quote") if isinstance(row.get("quote"), Mapping) else None
    reply = row.get("replying_to") if isinstance(row.get("replying_to"), Mapping) else None
    kind = "repost_snapshot" if repost else "quote" if quote else "reply" if reply else "post"
    target = quote.get("author") if quote and isinstance(quote.get("author"), Mapping) else reply
    target_author = ""
    if isinstance(target, Mapping):
        candidate = str(target.get("screen_name") or "").strip().lstrip("@").lower()
        target_author = candidate if _HANDLE.fullmatch(candidate) else ""
    target_text = content_text(quote) if quote else ""
    media_ids, media_urls = _media(row.get("media"))
    return XForensicAction(
        timeline_actor=actor,
        timeline_actor_id=actor_id,
        action_kind=kind,
        tweet_id=tweet_id,
        original_author=original,
        original_author_id=original_id,
        text=content_text(row),
        original_status_created_at=_timestamp(
            row.get("created_timestamp"), "status timestamp"
        ),
        exact_action_time_available=repost is None,
        target_author=target_author,
        target_text=target_text,
        media_ids=media_ids,
        media_urls=media_urls,
        likes_observed=_count(row.get("likes")),
        reposts_observed=_count(row.get("reposts")),
        replies_observed=_count(row.get("replies")),
        views_observed=_count(row.get("views")),
        fetched_at=_utc(fetched_at, "timeline fetched_at"),
    )


def _identity(value: object, field: str) -> tuple[str, str]:
    if not isinstance(value, Mapping):
        raise XForensicError(f"FxTwitter forensic {field} is missing")
    handle = str(value.get("screen_name") or "").strip().lstrip("@").lower()
    user_id = str(value.get("id") or "").strip()
    if not _HANDLE.fullmatch(handle) or not _ID.fullmatch(user_id):
        raise XForensicError(f"FxTwitter forensic {field} is invalid")
    return handle, user_id


def _handle(value: str) -> str:
    handle = value.strip().lstrip("@").lower()
    if not _HANDLE.fullmatch(handle):
        raise XForensicError("FxTwitter forensic expected handle is invalid")
    return handle


def _avatar_resource(url: str) -> tuple[str | None, datetime | None]:
    match = _AVATAR_ID.search(url)
    if not match:
        return None, None
    resource_id = match.group(1)
    milliseconds = (int(resource_id) >> 22) + _SNOWFLAKE_EPOCH_MS
    return resource_id, datetime.fromtimestamp(milliseconds / 1_000, timezone.utc)


def _banner_resource(url: str) -> datetime | None:
    match = _BANNER_TIME.search(url)
    if not match:
        return None
    return _timestamp(int(match.group(1)), "banner resource timestamp")


def _twitter_time(value: object, field: str) -> datetime:
    try:
        parsed = datetime.strptime(str(value), "%a %b %d %H:%M:%S %z %Y")
    except ValueError:
        raise XForensicError(f"FxTwitter forensic {field} is invalid") from None
    return parsed.astimezone(timezone.utc)


def _timestamp(value: object, field: str) -> datetime:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise XForensicError(f"FxTwitter forensic {field} is invalid")
    if not math.isfinite(float(value)):
        raise XForensicError(f"FxTwitter forensic {field} is invalid")
    try:
        return datetime.fromtimestamp(float(value), timezone.utc)
    except (OverflowError, OSError, ValueError):
        raise XForensicError(f"FxTwitter forensic {field} is invalid") from None


def _media(value: object) -> tuple[tuple[str, ...], tuple[str, ...]]:
    media = value if isinstance(value, Mapping) else {}
    rows = media.get("all") if isinstance(media.get("all"), list) else []
    ids, urls = [], []
    for row in rows[:16]:
        if not isinstance(row, Mapping):
            continue
        media_id = str(row.get("id") or "").strip()
        url = str(row.get("url") or "").strip()
        if _ID.fullmatch(media_id):
            ids.append(media_id)
        if url.startswith("https://") and len(url) <= 4_096:
            urls.append(url)
    return tuple(dict.fromkeys(ids)), tuple(dict.fromkeys(urls))


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _utc(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise XForensicError(f"FxTwitter forensic {field} must be timezone-aware")
    return value.astimezone(timezone.utc)
