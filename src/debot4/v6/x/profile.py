"""Stable-identity profile lookup through the public FxTwitter API."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Mapping
import urllib.parse

from .http import FxJsonHttp, FxTwitterError, JsonGetter
from .models import XCheckpoint, XProfile


_SHA256 = re.compile(r"[0-9a-f]{64}")


class XProfileError(FxTwitterError):
    """FxTwitter profile identity or schema failure."""


@dataclass(frozen=True, slots=True)
class XProfileObservation:
    profile: XProfile
    source_url: str
    response_bytes: int
    sha256: str
    response_identity: str | None

    def __post_init__(self) -> None:
        if not self.source_url.startswith("https://api.fxtwitter.com/"):
            raise ValueError("X profile evidence URL is invalid")
        if self.response_bytes <= 0 or not _SHA256.fullmatch(self.sha256):
            raise ValueError("X profile evidence receipt is invalid")


@dataclass(slots=True)
class XProfileClient:
    http: JsonGetter = field(default_factory=FxJsonHttp)
    origin: str = "https://api.fxtwitter.com"

    def __post_init__(self) -> None:
        parsed = urllib.parse.urlsplit(self.origin)
        if parsed.scheme != "https" or not parsed.hostname or parsed.path.rstrip("/"):
            raise ValueError("FxTwitter origin must be an HTTPS origin")
        self.origin = self.origin.rstrip("/")

    def fetch(self, handle: str) -> XProfile:
        return self.fetch_observation(handle).profile

    def fetch_observation(self, handle: str) -> XProfileObservation:
        expected = XCheckpoint(handle).handle
        encoded = urllib.parse.quote(expected, safe="")
        source_url = f"{self.origin}/{encoded}"
        document = self.http.get_json(source_url)
        if document is None:
            raise XProfileError("FxTwitter returned an empty profile")
        profile = parse_fxtwitter_profile(
            document.payload,
            expected_handle=expected,
            fetched_at=document.fetched_at,
        )
        if not document.sha256:
            raise XProfileError("FxTwitter profile response fingerprint is missing")
        return XProfileObservation(
            profile, source_url, document.response_bytes,
            document.sha256, document.response_identity,
        )


def parse_fxtwitter_profile(
    payload: object, *, expected_handle: str, fetched_at
) -> XProfile:
    if not isinstance(payload, Mapping) or payload.get("code") != 200:
        raise XProfileError("FxTwitter profile schema is invalid")
    user = payload.get("user")
    if not isinstance(user, Mapping):
        raise XProfileError("FxTwitter profile schema is invalid")
    try:
        profile = XProfile(
            handle=str(user.get("screen_name") or ""),
            user_id=str(user.get("id") or ""),
            display_name=str(user.get("name") or ""),
            description=str(user.get("description") or ""),
            fetched_at=fetched_at,
        )
    except (TypeError, ValueError) as exc:
        raise XProfileError("FxTwitter profile identity is invalid") from exc
    if profile.handle != XCheckpoint(expected_handle).handle:
        raise XProfileError("FxTwitter returned an unexpected profile handle")
    return profile
