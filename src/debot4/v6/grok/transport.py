"""Sanitized HTTP transport for Grok2API."""

from __future__ import annotations

import json
from typing import Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class GrokApiError(RuntimeError):
    """A sanitized Grok2API transport or response failure."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class JsonTransport(Protocol):
    def post_json(
        self,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> Mapping[str, object]: ...


class UrlLibTransport:
    def post_json(
        self,
        url: str,
        headers: Mapping[str, str],
        payload: Mapping[str, object],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        request = Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=dict(headers),
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            raise GrokApiError(
                f"Grok2API HTTP {exc.code}",
                retryable=exc.code in {429, 502, 503, 504},
            ) from exc
        except TimeoutError as exc:
            raise GrokApiError(
                "Grok2API request timed out", retryable=True
            ) from exc
        except URLError as exc:
            raise GrokApiError(
                "Grok2API request failed", retryable=True
            ) from exc
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GrokApiError("Grok2API returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise GrokApiError("Grok2API returned a non-object response")
        return value
