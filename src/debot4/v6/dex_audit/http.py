"""Small bounded JSON HTTP client for explicitly allowed public APIs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import json
from time import monotonic
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .models import HttpAttempt, JsonResponse


UTC = timezone.utc
ALLOWED_HOSTS = frozenset({"dapi.coinmarketcap.com", "api.geckoterminal.com"})


def _now_us() -> int:
    return int(datetime.now(UTC).timestamp() * 1_000_000)


class DirectJsonClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = 8.0,
        max_response_bytes: int = 2_000_000,
        opener: Callable[..., Any] = urlopen,
        clock_us: Callable[[], int] = _now_us,
        timer: Callable[[], float] = monotonic,
    ) -> None:
        if timeout_seconds <= 0 or max_response_bytes <= 0:
            raise ValueError("HTTP bounds must be positive")
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self._opener = opener
        self._clock_us = clock_us
        self._timer = timer

    def request_json(
        self,
        *,
        source: str,
        method: str,
        url: str,
        body: dict[str, object] | None = None,
    ) -> JsonResponse:
        self._validate_url(url)
        encoded = None
        request_json = None
        if body is not None:
            request_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
            encoded = request_json.encode("utf-8")
        headers = {
            "Accept": "application/json",
            "User-Agent": "debot4-v6-dex-audit/1",
        }
        if encoded is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=encoded, headers=headers, method=method.upper())
        started_at_us = self._clock_us()
        started = self._timer()
        status: int | None = None
        size = 0
        failure: str | None = None
        payload: Any | None = None
        try:
            with self._opener(request, timeout=self.timeout_seconds) as response:
                status = int(response.status)
                raw = response.read(self.max_response_bytes + 1)
                size = len(raw)
                if size > self.max_response_bytes:
                    raise ValueError("response exceeds byte limit")
                payload = json.loads(raw.decode("utf-8"))
        except HTTPError as exc:
            status = int(exc.code)
            failure = f"HTTP {exc.code}: {exc.reason}"
        except URLError as exc:
            failure = f"network error: {exc.reason}"
        except (UnicodeError, json.JSONDecodeError) as exc:
            failure = f"invalid JSON: {type(exc).__name__}"
        except (OSError, TimeoutError, ValueError) as exc:
            failure = f"{type(exc).__name__}: {str(exc)[:180]}"
        completed_at_us = self._clock_us()
        latency_ms = max(0, round((self._timer() - started) * 1_000))
        attempt = HttpAttempt(
            source=source,
            method=method.upper(),
            url=url,
            request_json=request_json,
            started_at_us=started_at_us,
            completed_at_us=completed_at_us,
            latency_ms=latency_ms,
            http_status=status,
            response_bytes=size,
            success=failure is None and 200 <= (status or 0) < 300,
            failure_reason=failure,
        )
        return JsonResponse(payload if attempt.success else None, attempt)

    @staticmethod
    def _validate_url(url: str) -> None:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in ALLOWED_HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ValueError("DEX audit URL is not allowlisted")
