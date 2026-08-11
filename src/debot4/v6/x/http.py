"""Small hardened JSON transport shared by FxTwitter adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Callable, Protocol
import urllib.error
import urllib.parse
import urllib.request

from .egress import FxEgressError, RequestOpener, direct_opener


class FxTwitterError(RuntimeError):
    """A sanitized FxTwitter transport or response failure."""


@dataclass(frozen=True, slots=True)
class FxJsonDocument:
    payload: object
    fetched_at: datetime
    response_bytes: int


class JsonGetter(Protocol):
    def get_json(self, url: str) -> FxJsonDocument | None: ...


@dataclass(slots=True)
class FxJsonHttp:
    timeout_seconds: float = 8.0
    max_response_bytes: int = 2_000_000
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    allowed_hosts: tuple[str, ...] = ("api.fxtwitter.com",)
    opener: RequestOpener | None = None

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("FxTwitter timeout must be positive")
        if not 1_024 <= self.max_response_bytes <= 8 * 1_024 * 1_024:
            raise ValueError("FxTwitter byte limit is invalid")
        if self.opener is None:
            self.opener = direct_opener()

    def get_json(self, url: str) -> FxJsonDocument | None:
        self._validate_url(url)
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "debot4-v6/0.1"},
            method="GET",
        )
        try:
            with self.opener.open(request, timeout=self.timeout_seconds) as response:
                status = int(response.status)
                if response.geturl() != url or status not in {200, 204}:
                    raise FxTwitterError("FxTwitter returned an unexpected response")
                if status == 204:
                    return None
                raw = response.read(self.max_response_bytes + 1)
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
        return FxJsonDocument(payload, _utc(self.clock()), len(raw))

    def _validate_url(self, url: str) -> None:
        parsed = urllib.parse.urlsplit(url)
        hosts = {item.casefold() for item in self.allowed_hosts}
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.hostname.casefold() not in hosts
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in {None, 443}
            or parsed.fragment
        ):
            raise ValueError("FxTwitter URL is outside the configured HTTPS origin")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("FxTwitter clock must be timezone-aware")
    return value.astimezone(timezone.utc)
