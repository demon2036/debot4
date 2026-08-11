"""Stable-identity profile lookup through the public FxTwitter API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping
import urllib.parse

from .http import FxJsonHttp, FxTwitterError, JsonGetter
from .models import XCheckpoint, XProfile


class XProfileError(FxTwitterError):
    """FxTwitter profile identity or schema failure."""


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
        expected = XCheckpoint(handle).handle
        encoded = urllib.parse.quote(expected, safe="")
        document = self.http.get_json(f"{self.origin}/{encoded}")
        if document is None:
            raise XProfileError("FxTwitter returned an empty profile")
        return parse_fxtwitter_profile(
            document.payload,
            expected_handle=expected,
            fetched_at=document.fetched_at,
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
