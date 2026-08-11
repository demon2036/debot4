"""Poll reviewed X accounts through the public FxTwitter timeline API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import math
import re
from typing import Callable, Mapping
import urllib.parse

from .content import content_text
from .http import FxJsonHttp, FxTwitterError, JsonGetter
from .models import XCheckpoint, XPost, XTimelineBatch


FXTWITTER_API_ORIGIN = "https://api.fxtwitter.com"
_HANDLE = re.compile(r"[A-Za-z0-9_]{1,15}")
_ID = re.compile(r"[1-9][0-9]{5,24}")
_BSC_CA = re.compile(r"(?<![0-9A-Fa-f])0x[0-9A-Fa-f]{40}(?![0-9A-Fa-f])")
_URL = re.compile(r"https?://[^\s<>\"]{1,2048}")
_SNOWFLAKE_EPOCH_MS = 1_288_834_974_657


class XTimelineError(FxTwitterError):
    """A sanitized FxTwitter transport, identity, or schema failure."""


@dataclass(slots=True)
class XTimelineClient:
    """Incremental, browser-free X timeline client with stable-ID checks."""

    http: JsonGetter = field(default_factory=FxJsonHttp)
    origin: str = FXTWITTER_API_ORIGIN
    limit: int = 20
    initial_lookback_seconds: float = 6 * 60 * 60
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)

    def __post_init__(self) -> None:
        parsed = urllib.parse.urlsplit(self.origin)
        if parsed.scheme != "https" or not parsed.hostname or parsed.path.rstrip("/"):
            raise ValueError("FxTwitter origin must be an HTTPS origin")
        if not 1 <= self.limit <= 100:
            raise ValueError("X timeline limit must be between 1 and 100")
        if not 0 < self.initial_lookback_seconds <= 24 * 60 * 60:
            raise ValueError("initial X lookback must be within 24 hours")
        self.origin = self.origin.rstrip("/")

    def poll(self, handle: str, checkpoint: XCheckpoint | None = None) -> XTimelineBatch:
        state = checkpoint or XCheckpoint(handle)
        if state.handle != XCheckpoint(handle).handle:
            raise ValueError("X checkpoint handle mismatch")
        since = _since_seconds(state, _utc(self.clock(), "clock"), self.initial_lookback_seconds)
        query = urllib.parse.urlencode({"count": self.limit, "since": since})
        encoded = urllib.parse.quote(state.handle, safe="")
        document = self.http.get_json(
            f"{self.origin}/2/profile/{encoded}/statuses?{query}"
        )
        if document is None:
            if not state.user_id:
                raise XTimelineError("empty timeline cannot establish actor identity")
            return XTimelineBatch((), state, 0, 1)
        posts, actor_id, fetched_items = parse_fxtwitter_timeline(
            document.payload,
            expected_handle=state.handle,
            expected_author_id=state.user_id,
            fetched_at=document.fetched_at,
        )
        selected = [
            post for post in posts
            if not state.latest_tweet_id or int(post.tweet_id) > int(state.latest_tweet_id)
        ]
        selected.sort(key=lambda item: (int(item.tweet_id), item.created_at))
        newest = max((post.tweet_id for post in posts), key=int, default="")
        latest = max((state.latest_tweet_id, newest), key=lambda value: int(value or "0"))
        return XTimelineBatch(
            posts=tuple(selected[-self.limit:]),
            checkpoint=XCheckpoint(state.handle, actor_id, latest),
            fetched_items=fetched_items,
            request_count=1,
        )


def parse_fxtwitter_timeline(
    payload: object,
    *,
    expected_handle: str,
    expected_author_id: str,
    fetched_at: datetime,
) -> tuple[tuple[XPost, ...], str, int]:
    if not isinstance(payload, Mapping) or payload.get("code") != 200:
        raise XTimelineError("FxTwitter timeline schema is invalid")
    rows = payload.get("results")
    if not isinstance(rows, list) or len(rows) > 100:
        raise XTimelineError("FxTwitter timeline schema is invalid")
    handle = XCheckpoint(expected_handle).handle
    actor_ids: set[str] = set()
    posts: dict[str, XPost] = {}
    for row in rows:
        if not isinstance(row, Mapping) or row.get("type") != "status":
            continue
        actor = row.get("reposted_by") or row.get("author")
        actor_handle, actor_id = _identity(actor)
        if actor_handle != handle:
            raise XTimelineError("FxTwitter returned an untrusted actor handle")
        if expected_author_id and actor_id != expected_author_id:
            raise XTimelineError("FxTwitter returned an untrusted actor identity")
        actor_ids.add(actor_id)
        if row.get("reposted_by") is not None:
            continue
        post = _post(row, handle, fetched_at)
        posts[post.tweet_id] = post
    if len(actor_ids) > 1:
        raise XTimelineError("FxTwitter returned conflicting actor identities")
    actor_id = next(iter(actor_ids), expected_author_id)
    if not actor_id:
        raise XTimelineError("FxTwitter returned no stable actor identity")
    return tuple(posts.values()), actor_id, len(rows)


def _post(row: Mapping[str, object], handle: str, fetched_at: datetime) -> XPost:
    tweet_id = str(row.get("id") or "").strip()
    text = content_text(row)
    stamp = row.get("created_timestamp")
    if not _ID.fullmatch(tweet_id) or not text or len(text) > 100_000:
        raise XTimelineError("FxTwitter status schema is invalid")
    if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or not math.isfinite(stamp):
        raise XTimelineError("FxTwitter status timestamp is invalid")
    try:
        created_at = datetime.fromtimestamp(float(stamp), timezone.utc)
    except (OverflowError, OSError, ValueError):
        raise XTimelineError("FxTwitter status timestamp is invalid") from None
    quote = row.get("quote") if isinstance(row.get("quote"), Mapping) else {}
    reply = row.get("replying_to") if isinstance(row.get("replying_to"), Mapping) else {}
    post_type = "quote" if quote else "reply" if reply else "post"
    target = quote.get("author") if isinstance(quote.get("author"), Mapping) else reply
    target_handle = str(target.get("screen_name") or "") if isinstance(target, Mapping) else ""
    target_text = str(quote.get("text") or "").strip()[:100_000]
    urls = _urls(row, text)
    contracts = tuple(sorted({
        match.group(0).lower()
        for candidate in (text, target_text, *urls)
        for match in _BSC_CA.finditer(candidate)
    }))
    return XPost(
        tweet_id, handle, text, created_at, fetched_at, post_type,
        target_handle, target_text, urls, contracts,
    )


def _identity(value: object) -> tuple[str, str]:
    if not isinstance(value, Mapping):
        raise XTimelineError("FxTwitter actor identity is missing")
    handle = str(value.get("screen_name") or "").strip().lstrip("@").lower()
    actor_id = str(value.get("id") or "").strip()
    if not _HANDLE.fullmatch(handle) or not _ID.fullmatch(actor_id):
        raise XTimelineError("FxTwitter actor identity is invalid")
    return handle, actor_id


def _urls(row: Mapping[str, object], text: str) -> tuple[str, ...]:
    found = [match.group(0).rstrip(".,);]") for match in _URL.finditer(text)]
    raw = row.get("raw_text")
    facets = raw.get("facets") if isinstance(raw, Mapping) else []
    for facet in facets if isinstance(facets, list) else []:
        if not isinstance(facet, Mapping):
            continue
        value = str(facet.get("replacement") or facet.get("original") or "").strip()
        if value.startswith(("https://", "http://")) and len(value) <= 2_048:
            found.append(value)
    return tuple(dict.fromkeys(found[:32]))


def _since_seconds(state: XCheckpoint, now: datetime, lookback: float) -> int:
    if not state.latest_tweet_id:
        return max(0, int((now - timedelta(seconds=lookback)).timestamp()))
    milliseconds = (int(state.latest_tweet_id) >> 22) + _SNOWFLAKE_EPOCH_MS
    return max(0, milliseconds // 1000 - 2)


def _utc(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc)
