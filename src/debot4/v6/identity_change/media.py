"""Bounded, no-redirect downloads for X profile image evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from typing import Callable
import urllib.error
import urllib.parse
import urllib.request

from ..x.egress import RequestOpener, direct_opener


@dataclass(frozen=True, slots=True)
class ProfileMediaReceipt:
    source_url: str
    fetched_at: datetime
    response_bytes: int
    sha256: str
    content_type: str


@dataclass(slots=True)
class ProfileMediaClient:
    timeout_seconds: float = 6.0
    max_response_bytes: int = 5_000_000
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    opener: RequestOpener | None = field(default=None)

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0 or not 1_024 <= self.max_response_bytes <= 8_000_000:
            raise ValueError("profile media limits are invalid")
        if self.opener is None:
            self.opener = direct_opener()

    def fetch(self, url: str) -> ProfileMediaReceipt:
        parsed = urllib.parse.urlsplit(url)
        if (
            parsed.scheme != "https" or parsed.hostname != "pbs.twimg.com"
            or parsed.username is not None or parsed.password is not None
            or parsed.port not in {None, 443} or parsed.fragment
        ):
            raise ValueError("profile media URL is outside pbs.twimg.com")
        request = urllib.request.Request(
            url, headers={"Accept": "image/*", "User-Agent": "debot4-v6/0.1"}
        )
        try:
            with self.opener.open(request, timeout=self.timeout_seconds) as response:
                if response.geturl() != url or int(response.status) != 200:
                    raise RuntimeError("profile media returned an unexpected response")
                raw = response.read(self.max_response_bytes + 1)
                content_type = str(response.headers.get("content-type") or "")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError("profile media connection failed") from exc
        if len(raw) > self.max_response_bytes or not raw:
            raise RuntimeError("profile media response size is invalid")
        if not content_type.casefold().startswith("image/"):
            raise RuntimeError("profile media response is not an image")
        fetched = self.clock()
        if fetched.tzinfo is None or fetched.utcoffset() is None:
            raise ValueError("profile media clock must be timezone-aware")
        return ProfileMediaReceipt(
            url, fetched.astimezone(timezone.utc), len(raw),
            hashlib.sha256(raw).hexdigest(), content_type,
        )
