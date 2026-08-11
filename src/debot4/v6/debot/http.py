"""Persistent, bounded HTTPS transport for DeBot's official API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urlsplit

import httpx

from .credentials import DeBotCredentialError, load_debot_cookies


UTC = timezone.utc


class DeBotApiError(RuntimeError):
    """Sanitized DeBot authentication, transport, or schema failure."""


@dataclass(frozen=True, slots=True)
class JsonDocument:
    url: str
    fetched_at: datetime
    bytes_read: int
    payload: dict[str, Any]


class DeBotHttp:
    def __init__(
        self,
        *,
        credential_file: str | Path,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> None:
        self.credential_file = Path(credential_file).expanduser().resolve()
        self.timeout = float(timeout_seconds)
        self.max_bytes = int(max_response_bytes)
        self._client: httpx.Client | None = None
        self._credential_revision: tuple[int, int, int, int] | None = None
        self._lock = Lock()

    def close(self) -> None:
        with self._lock:
            if self._client is not None:
                self._client.close()
                self._client = None

    def get_json(self, url: str) -> JsonDocument:
        _validate_url(url)
        with self._lock:
            client = self._get_client()
            try:
                response = client.get(url)
            except httpx.HTTPError as exc:
                raise DeBotApiError("DeBot API connection failed") from exc
        fetched_at = datetime.now(UTC)
        _validate_url(str(response.url))
        if response.status_code != 200:
            if response.status_code in {401, 403}:
                self._credential_revision = None
                raise DeBotApiError("DeBot authentication expired")
            raise DeBotApiError(f"DeBot API returned HTTP {response.status_code}")
        raw = response.content
        if len(raw) > self.max_bytes:
            raise DeBotApiError("DeBot API response exceeded the byte limit")
        try:
            payload = response.json()
        except ValueError as exc:
            raise DeBotApiError("DeBot API returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise DeBotApiError("DeBot API JSON root is not an object")
        return JsonDocument(str(response.url), fetched_at, len(raw), payload)

    def _get_client(self) -> httpx.Client:
        revision = self._revision()
        if self._client is not None and revision == self._credential_revision:
            assert self._client is not None
            return self._client
        try:
            cookies = load_debot_cookies(self.credential_file)
        except DeBotCredentialError as exc:
            raise DeBotApiError("DeBot credential file is invalid") from exc
        if self._client is not None:
            self._client.close()
        jar = httpx.Cookies()
        for item in cookies:
            jar.set(
                item.name, item.value, domain=item.domain, path=item.path,
            )
        self._client = httpx.Client(
            cookies=jar,
            timeout=self.timeout,
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
            headers={
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache, no-store, max-age=0",
                "Origin": "https://app.debot.ai",
                "Pragma": "no-cache",
                "Referer": "https://app.debot.ai/signal?chain=bsc",
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "Chrome/121.0.0.0 Safari/537.36"
                ),
            },
        )
        self._credential_revision = revision
        return self._client

    def _revision(self) -> tuple[int, int, int, int]:
        try:
            metadata = self.credential_file.stat()
        except OSError as exc:
            raise DeBotApiError("DeBot credential file is unavailable") from exc
        return (
            metadata.st_dev, metadata.st_ino,
            metadata.st_mtime_ns, metadata.st_size,
        )


def _validate_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "app.debot.ai"
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
        or parsed.path not in {
            "/api/community/signal/channel/list",
            "/api/dashboard/meme/v3/ranks",
        }
        or parsed.fragment
    ):
        raise DeBotApiError("DeBot API URL is outside the allowlist")
