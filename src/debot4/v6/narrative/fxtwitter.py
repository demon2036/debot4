"""Strict, browser-free FxTwitter lookup owned entirely by v6."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Callable
import urllib.error
import urllib.parse
import urllib.request

from ..x.content import content_text
from ..x.egress import FxEgressError, RequestOpener, direct_opener

FXTWITTER_API_ORIGIN = "https://api.fxtwitter.com"
_HANDLE = re.compile(r"[A-Za-z0-9_]{1,15}")
_STATUS_ID = re.compile(r"[1-9][0-9]{5,24}")
_X_HOSTS = frozenset({
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "fxtwitter.com",
    "www.fxtwitter.com",
})


class FxTwitterError(RuntimeError):
    """Sanitized URL, transport, or schema failure."""


@dataclass(frozen=True, slots=True)
class FxTwitterTweet:
    tweet_id: str
    author_handle: str
    author_id: str | None
    text: str
    published_at: datetime
    fetched_at: datetime
    canonical_url: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "published_at", _aware_utc(self.published_at, "published_at"))
        object.__setattr__(self, "fetched_at", _aware_utc(self.fetched_at, "fetched_at"))
        if not _STATUS_ID.fullmatch(self.tweet_id):
            raise ValueError("tweet_id is invalid")
        if not _HANDLE.fullmatch(self.author_handle):
            raise ValueError("author_handle is invalid")
        if not self.text.strip() or len(self.text) > 100_000:
            raise ValueError("tweet text is invalid")


@dataclass(frozen=True, slots=True)
class FxTwitterObservation:
    """Parsed tweet plus the exact bounded provider bytes used to verify it."""

    tweet: FxTwitterTweet
    raw_payload: bytes
    response_identity: str

    def __post_init__(self) -> None:
        if not isinstance(self.raw_payload, bytes) or not self.raw_payload:
            raise ValueError("raw FxTwitter payload is required")
        if not self.response_identity.strip():
            raise ValueError("FxTwitter response identity is required")


class FxTwitterClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 8.0,
        max_response_bytes: int = 1024 * 1024,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        opener: RequestOpener | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not 1024 <= max_response_bytes <= 4 * 1024 * 1024:
            raise ValueError("max_response_bytes must be between 1 KiB and 4 MiB")
        self.timeout_seconds = float(timeout_seconds)
        self.max_response_bytes = int(max_response_bytes)
        self.clock = clock
        self.opener = opener or direct_opener()

    def fetch_status(self, status_url: str) -> FxTwitterTweet:
        return self.fetch_observation(status_url).tweet

    def fetch_observation(self, status_url: str) -> FxTwitterObservation:
        handle, tweet_id = parse_x_status_url(status_url)
        url = f"{FXTWITTER_API_ORIGIN}/{handle}/status/{tweet_id}"
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "debot4-v6/0.1"},
            method="GET",
        )
        try:
            with self.opener.open(request, timeout=self.timeout_seconds) as response:
                if response.geturl() != url or int(response.status) != 200:
                    raise FxTwitterError("FxTwitter returned an unexpected response")
                raw = response.read(self.max_response_bytes + 1)
                response_id = _response_identity(response.headers, raw)
        except FxTwitterError:
            raise
        except urllib.error.HTTPError as exc:
            raise FxTwitterError(f"FxTwitter returned HTTP {exc.code}") from None
        except (FxEgressError, urllib.error.URLError, TimeoutError, OSError):
            raise FxTwitterError("FxTwitter connection failed") from None
        if len(raw) > self.max_response_bytes:
            raise FxTwitterError("FxTwitter response exceeded the byte limit")
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise FxTwitterError("FxTwitter returned invalid JSON") from None
        tweet = parse_fxtwitter_payload(
            payload, expected_id=tweet_id, fetched_at=self.clock()
        )
        return FxTwitterObservation(tweet, raw, response_id)


def parse_x_status_url(url: str) -> tuple[str, str]:
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except (TypeError, ValueError):
        raise FxTwitterError("X status URL is invalid") from None
    host = (parsed.hostname or "").lower().rstrip(".")
    parts = [urllib.parse.unquote(item) for item in parsed.path.split("/") if item]
    if (
        parsed.scheme.lower() != "https"
        or host not in _X_HOSTS
        or port not in (None, 443)
        or parsed.username
        or parsed.password
        or len(parts) != 3
        or parts[1].lower() != "status"
        or not _HANDLE.fullmatch(parts[0])
        or not _STATUS_ID.fullmatch(parts[2])
    ):
        raise FxTwitterError("X status URL is outside the allowlist")
    return parts[0], parts[2]


def parse_fxtwitter_payload(
    payload: object,
    *,
    expected_id: str,
    fetched_at: datetime,
) -> FxTwitterTweet:
    if not isinstance(payload, dict) or payload.get("code") != 200:
        raise FxTwitterError("FxTwitter response schema is invalid")
    tweet = payload.get("tweet")
    author = tweet.get("author") if isinstance(tweet, dict) else None
    if not isinstance(tweet, dict) or not isinstance(author, dict):
        raise FxTwitterError("FxTwitter response schema is invalid")
    tweet_id = str(tweet.get("id") or "")
    handle = str(author.get("screen_name") or "")
    text = content_text(tweet)
    published = tweet.get("created_timestamp")
    if (
        tweet_id != expected_id
        or not _HANDLE.fullmatch(handle)
        or not text
        or len(text) > 100_000
        or isinstance(published, bool)
        or not isinstance(published, (int, float))
    ):
        raise FxTwitterError("FxTwitter response schema is invalid")
    try:
        published_at = datetime.fromtimestamp(float(published), timezone.utc)
    except (OverflowError, OSError, ValueError):
        raise FxTwitterError("FxTwitter timestamp is invalid") from None
    return FxTwitterTweet(
        tweet_id=tweet_id,
        author_handle=handle,
        author_id=str(author.get("id") or "").strip() or None,
        text=text,
        published_at=published_at,
        fetched_at=_aware_utc(fetched_at, "fetched_at"),
        canonical_url=f"https://x.com/{handle}/status/{tweet_id}",
    )


def _aware_utc(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _response_identity(headers: object, raw: bytes) -> str:
    getter = getattr(headers, "get", None)
    if callable(getter):
        for name in ("x-request-id", "cf-ray", "etag"):
            value = str(getter(name) or "").strip()
            if value:
                return f"{name}:{value[:256]}"
    return f"sha256:{sha256(raw).hexdigest()}"
