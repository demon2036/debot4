"""Hardened HTML transport for public t.me pages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol
import urllib.error
import urllib.parse
import urllib.request


class TelegramHttpError(RuntimeError):
    """A sanitized Telegram transport or response failure."""


@dataclass(frozen=True, slots=True)
class TelegramHtmlDocument:
    html: str
    fetched_at: datetime
    response_bytes: int


class TelegramHtmlGetter(Protocol):
    def get_html(self, url: str) -> TelegramHtmlDocument: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


@dataclass(slots=True)
class TelegramHtmlHttp:
    timeout_seconds: float = 8.0
    max_response_bytes: int = 2_000_000
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)

    def get_html(self, url: str) -> TelegramHtmlDocument:
        self._validate_url(url)
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": "debot4-v6/0.1",
            },
            method="GET",
        )
        try:
            with urllib.request.build_opener(_NoRedirect()).open(
                request, timeout=self.timeout_seconds
            ) as response:
                if response.geturl() != url or int(response.status) != 200:
                    raise TelegramHttpError("Telegram returned an unexpected response")
                raw = response.read(self.max_response_bytes + 1)
        except TelegramHttpError:
            raise
        except urllib.error.HTTPError as exc:
            raise TelegramHttpError(f"Telegram returned HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TelegramHttpError("Telegram connection failed") from None
        if len(raw) > self.max_response_bytes:
            raise TelegramHttpError("Telegram response exceeded the byte limit")
        try:
            html = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise TelegramHttpError("Telegram returned invalid UTF-8") from None
        fetched_at = self.clock()
        if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
            raise ValueError("Telegram HTTP clock must be timezone-aware")
        return TelegramHtmlDocument(
            html, fetched_at.astimezone(timezone.utc), len(raw)
        )

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urllib.parse.urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "t.me"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in {None, 443}
            or parsed.fragment
        ):
            raise ValueError("Telegram URL is outside the configured HTTPS origin")
