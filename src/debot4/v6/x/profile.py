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
        source_url = f"{self.origin}/2/profile/{encoded}?about_account=1"
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
    website = user.get("website")
    verification = user.get("verification")
    about = user.get("about_account")
    changes = about.get("username_changes") if isinstance(about, Mapping) else None
    try:
        profile = XProfile(
            handle=str(user.get("screen_name") or ""),
            user_id=str(user.get("id") or ""),
            display_name=str(user.get("name") or ""),
            description=str(user.get("description") or ""),
            fetched_at=fetched_at,
            avatar_url=str(user.get("avatar_url") or ""),
            banner_url=str(user.get("banner_url") or ""),
            location=str(user.get("location") or ""),
            profile_url=str(user.get("url") or ""),
            website_url=_nested_text(website, "url"),
            website_display=_nested_text(website, "display_url"),
            verified=_nested_bool(verification, "verified"),
            verification_type=_nested_text(verification, "type"),
            protected=_bool(user.get("protected")),
            followers=_count(user.get("followers")),
            following=_count(user.get("following")),
            statuses=_count(user.get("statuses")),
            media_count=_count(user.get("media_count")),
            likes=_count(user.get("likes")),
            joined=str(user.get("joined") or ""),
            based_in=_nested_text(about, "based_in"),
            username_change_count=_nested_count(changes, "count"),
            username_changed_at=_nested_text(changes, "last_changed_at"),
        )
    except (TypeError, ValueError) as exc:
        raise XProfileError("FxTwitter profile identity is invalid") from exc
    if profile.handle != XCheckpoint(expected_handle).handle:
        raise XProfileError("FxTwitter returned an unexpected profile handle")
    return profile


def _nested_text(value: object, key: str) -> str:
    return str(value.get(key) or "") if isinstance(value, Mapping) else ""


def _nested_count(value: object, key: str) -> int:
    return _count(value.get(key)) if isinstance(value, Mapping) else 0


def _nested_bool(value: object, key: str) -> bool:
    return _bool(value.get(key)) if isinstance(value, Mapping) else False


def _count(value: object) -> int:
    if isinstance(value, bool) or value is None:
        return 0
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(parsed, 0)


def _bool(value: object) -> bool:
    return value is True or str(value).strip().casefold() == "true"
