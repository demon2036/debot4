"""Shared bounded HTTP transport for anonymous GMGN evidence adapters."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Mapping

import httpx

from .models import EvidenceReceipt


BASE_URL = "https://gmgn.ai"


class GmgnTransportError(RuntimeError):
    """Sanitized GMGN transport or response-envelope failure."""


class GmgnPublicTransport:
    def __init__(self, *, timeout_seconds: float = 30, attempts: int = 3,
                 client: httpx.Client | None = None) -> None:
        if timeout_seconds <= 0 or not 1 <= attempts <= 5:
            raise ValueError("invalid GMGN transport bounds")
        self.attempts = attempts
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=BASE_URL,
            timeout=timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": f"{BASE_URL}/",
                "User-Agent": "Googlebot",
            },
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def request_json(
        self, method: str, path: str, *, body: Mapping[str, object] | None = None,
    ) -> tuple[dict[str, Any], EvidenceReceipt]:
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                response = self._client.request(method, path, json=body)
                if response.status_code != 200:
                    raise GmgnTransportError(
                        f"GMGN public API returned HTTP {response.status_code}",
                    )
                raw = response.content
                if len(raw) > 8_000_000:
                    raise GmgnTransportError("GMGN response exceeded byte limit")
                payload = response.json()
                if not isinstance(payload, dict) or payload.get("code") != 0:
                    raise GmgnTransportError("GMGN returned an unsuccessful envelope")
                return payload, EvidenceReceipt(
                    kind="gmgn_public_json",
                    url=str(response.url),
                    fetched_at=int(time.time()),
                    sha256=hashlib.sha256(raw).hexdigest(),
                )
            except (httpx.HTTPError, json.JSONDecodeError, GmgnTransportError) as exc:
                last_error = exc
                if attempt + 1 < self.attempts:
                    delay = 5.0 * (2**attempt) if (
                        isinstance(exc, GmgnTransportError)
                        and "HTTP 429" in str(exc)
                    ) else 0.25 * (2**attempt)
                    time.sleep(delay)
        raise GmgnTransportError("GMGN public API request failed") from last_error
