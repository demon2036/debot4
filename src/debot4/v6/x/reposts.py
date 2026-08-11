"""Low-latency FxTwitter repost canary isolated from narrative decisions."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import re
from threading import Lock
from time import monotonic
from typing import Callable, Mapping
import urllib.parse

from .content import content_text
from .http import FxJsonHttp, FxTwitterError, JsonGetter


FXTWITTER_API_ORIGIN = "https://api.fxtwitter.com"
DEFAULT_REPOST_POLL_SECONDS = 1.0
_HANDLE = re.compile(r"[A-Za-z0-9_]{1,15}")
_ID = re.compile(r"[1-9][0-9]{5,24}")


class XRepostError(FxTwitterError):
    """A sanitized repost timeline or identity failure."""


@dataclass(frozen=True, slots=True)
class XRepostTarget:
    handle: str
    author_id: str
    interval_seconds: float = DEFAULT_REPOST_POLL_SECONDS

    def __post_init__(self) -> None:
        handle = self.handle.strip().lstrip("@").lower()
        seconds = float(self.interval_seconds)
        if not _HANDLE.fullmatch(handle) or not _ID.fullmatch(self.author_id):
            raise ValueError("repost target requires a stable X identity")
        if not math.isfinite(seconds) or not 0.25 <= seconds <= 60:
            raise ValueError("repost poll interval must be between 0.25 and 60 seconds")
        object.__setattr__(self, "handle", handle)
        object.__setattr__(self, "interval_seconds", seconds)


@dataclass(frozen=True, slots=True)
class XRepostObservation:
    reposter: str
    reposter_id: str
    original_tweet_id: str
    original_author: str
    text: str
    original_created_at: datetime
    detected_at: datetime

    @property
    def canonical_url(self) -> str:
        return (
            f"https://x.com/{self.original_author}/status/"
            f"{self.original_tweet_id}"
        )

    def as_public_dict(self) -> dict[str, object]:
        return {
            "action": "repost",
            "reposter": self.reposter,
            "reposter_id": self.reposter_id,
            "original_tweet_id": self.original_tweet_id,
            "original_author": self.original_author,
            "text": self.text[:500],
            "original_created_at": self.original_created_at.isoformat(),
            "detected_at": self.detected_at.isoformat(),
            "source_url": self.canonical_url,
            "enters_narrative_queue": False,
        }


@dataclass(slots=True)
class FxTwitterRepostMonitor:
    """Detect newly observed repost IDs without treating old post time as action time."""

    targets: tuple[XRepostTarget, ...]
    http: JsonGetter = field(default_factory=FxJsonHttp)
    origin: str = FXTWITTER_API_ORIGIN
    limit: int = 20
    recent_limit: int = 50
    seen_limit: int = 2_048
    clock: Callable[[], float] = monotonic
    _next_due: dict[str, float] = field(init=False, repr=False)
    _initialized: set[str] = field(init=False, repr=False)
    _seen: dict[str, set[str]] = field(init=False, repr=False)
    _seen_order: dict[str, deque[str]] = field(init=False, repr=False)
    _recent: deque[XRepostObservation] = field(init=False, repr=False)
    _lock: Lock = field(init=False, repr=False)
    last_error_types: dict[str, str | None] = field(init=False)
    last_polled_at: datetime | None = field(init=False, default=None)
    last_polled_targets: int = field(init=False, default=0)
    total_events: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        parsed = urllib.parse.urlsplit(self.origin)
        if parsed.scheme != "https" or not parsed.hostname or parsed.path.rstrip("/"):
            raise ValueError("FxTwitter origin must be an HTTPS origin")
        if not 1 <= self.limit <= 100 or not 1 <= self.recent_limit <= 500:
            raise ValueError("invalid repost monitor result limit")
        if not self.recent_limit <= self.seen_limit <= 100_000:
            raise ValueError("invalid repost seen window")
        handles = [target.handle for target in self.targets]
        if len(handles) != len(set(handles)):
            raise ValueError("duplicate repost monitor target")
        self.targets = tuple(self.targets)
        self.origin = self.origin.rstrip("/")
        self._next_due = {target.handle: float("-inf") for target in self.targets}
        self._initialized: set[str] = set()
        self._seen = {target.handle: set() for target in self.targets}
        self._seen_order = {target.handle: deque() for target in self.targets}
        self._recent: deque[XRepostObservation] = deque(maxlen=self.recent_limit)
        self._lock = Lock()
        self.last_error_types: dict[str, str | None] = {
            target.handle: None for target in self.targets
        }
        self.last_polled_at: datetime | None = None
        self.last_polled_targets = 0
        self.total_events = 0

    def poll_once(self) -> tuple[XRepostObservation, ...]:
        now = _finite_monotonic(self.clock())
        due = [target for target in self.targets if self._next_due[target.handle] <= now]
        for target in due:
            self._next_due[target.handle] = now + target.interval_seconds
        found: list[XRepostObservation] = []
        for target in due:
            try:
                observations, fetched_at = self._fetch(target)
                fresh = self._accept(target, observations)
                found.extend(fresh)
                self.last_error_types[target.handle] = None
                self.last_polled_at = fetched_at
            except Exception as exc:
                self.last_error_types[target.handle] = type(exc).__name__
        self.last_polled_targets = len(due)
        return tuple(found)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "available": bool(self.targets),
                "configured_targets": len(self.targets),
                "initialized_targets": len(self._initialized),
                "target_poll_seconds": {
                    target.handle: target.interval_seconds for target in self.targets
                },
                "total_events": self.total_events,
                "recent_events": [item.as_public_dict() for item in self._recent],
                "last_error_types": dict(self.last_error_types),
                "last_polled_at": (
                    self.last_polled_at.isoformat() if self.last_polled_at else None
                ),
                "exact_action_time_available": False,
                "likes_supported": False,
                "enters_narrative_queue": False,
            }

    def _fetch(
        self, target: XRepostTarget
    ) -> tuple[dict[str, XRepostObservation], datetime]:
        query = urllib.parse.urlencode({"count": self.limit})
        handle = urllib.parse.quote(target.handle, safe="")
        document = self.http.get_json(
            f"{self.origin}/2/profile/{handle}/statuses?{query}"
        )
        if document is None or not isinstance(document.payload, Mapping):
            raise XRepostError("FxTwitter repost timeline is empty")
        payload = document.payload
        rows = payload.get("results")
        if payload.get("code") != 200 or not isinstance(rows, list) or len(rows) > 100:
            raise XRepostError("FxTwitter repost timeline schema is invalid")
        observations: dict[str, XRepostObservation] = {}
        for row in rows:
            if not isinstance(row, Mapping) or row.get("type") != "status":
                continue
            actor = row.get("reposted_by") or row.get("author")
            actor_handle, actor_id = _identity(actor)
            if actor_handle != target.handle or actor_id != target.author_id:
                raise XRepostError("FxTwitter returned an untrusted repost identity")
            if row.get("reposted_by") is None:
                continue
            tweet_id = str(row.get("id") or "").strip()
            original_handle, _ = _identity(row.get("author"))
            if not _ID.fullmatch(tweet_id):
                raise XRepostError("FxTwitter repost status identity is invalid")
            observations[tweet_id] = XRepostObservation(
                target.handle,
                target.author_id,
                tweet_id,
                original_handle,
                content_text(row),
                _timestamp(row.get("created_timestamp")),
                _utc(document.fetched_at),
            )
        return observations, _utc(document.fetched_at)

    def _accept(
        self,
        target: XRepostTarget,
        observations: dict[str, XRepostObservation],
    ) -> tuple[XRepostObservation, ...]:
        with self._lock:
            baseline = target.handle not in self._initialized
            fresh = () if baseline else tuple(
                item for key, item in observations.items()
                if key not in self._seen[target.handle]
            )
            self._remember(target.handle, tuple(observations))
            self._initialized.add(target.handle)
            for item in fresh:
                self._recent.appendleft(item)
            self.total_events += len(fresh)
            return fresh

    def _remember(self, handle: str, tweet_ids: tuple[str, ...]) -> None:
        seen = self._seen[handle]
        order = self._seen_order[handle]
        for tweet_id in tweet_ids:
            if tweet_id in seen:
                continue
            seen.add(tweet_id)
            order.append(tweet_id)
        while len(order) > self.seen_limit:
            seen.discard(order.popleft())


def _identity(value: object) -> tuple[str, str]:
    if not isinstance(value, Mapping):
        raise XRepostError("FxTwitter repost actor identity is missing")
    handle = str(value.get("screen_name") or "").strip().lstrip("@").lower()
    actor_id = str(value.get("id") or "").strip()
    if not _HANDLE.fullmatch(handle) or not _ID.fullmatch(actor_id):
        raise XRepostError("FxTwitter repost actor identity is invalid")
    return handle, actor_id


def _timestamp(value: object) -> datetime:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise XRepostError("FxTwitter repost timestamp is invalid")
    try:
        return datetime.fromtimestamp(float(value), timezone.utc)
    except (OverflowError, OSError, ValueError):
        raise XRepostError("FxTwitter repost timestamp is invalid") from None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise XRepostError("FxTwitter fetched time must be timezone-aware")
    return value.astimezone(timezone.utc)


def _finite_monotonic(value: float) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("repost monitor clock must return a finite number")
    return result
