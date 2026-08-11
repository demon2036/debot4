"""Decision-time GoPlus security snapshot for one exact BSC contract."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from threading import Lock
from typing import Any, Mapping

import httpx

from .domain import SecuritySnapshot
from .identity import bsc_address, json_safe


UTC = timezone.utc
BASE_URL = "https://api.gopluslabs.io/api/v1/token_security/56"


class SecurityApiError(RuntimeError):
    """Sanitized GoPlus transport or response failure."""


class GoPlusClient:
    def __init__(self, *, timeout_seconds: float = 4.0) -> None:
        self._client = httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
            headers={"Accept": "application/json", "User-Agent": "debot4-v6/1.0"},
        )
        self._lock = Lock()

    def close(self) -> None:
        self._client.close()

    def fetch(self, token_address: str) -> SecuritySnapshot:
        token = bsc_address(token_address)
        with self._lock:
            try:
                response = self._client.get(
                    BASE_URL, params={"contract_addresses": token}
                )
            except httpx.HTTPError as exc:
                raise SecurityApiError("GoPlus connection failed") from exc
        fetched_at = datetime.now(UTC)
        if response.status_code != 200:
            raise SecurityApiError(f"GoPlus returned HTTP {response.status_code}")
        if len(response.content) > 2 * 1024 * 1024:
            raise SecurityApiError("GoPlus response exceeded the byte limit")
        try:
            root = response.json()
        except ValueError as exc:
            raise SecurityApiError("GoPlus returned invalid JSON") from exc
        if not isinstance(root, Mapping) or root.get("code") not in {1, "1"}:
            raise SecurityApiError("GoPlus response was unsuccessful")
        result = root.get("result")
        if not isinstance(result, Mapping):
            raise SecurityApiError("GoPlus result is missing")
        raw = result.get(token) or result.get(token.lower())
        if not isinstance(raw, Mapping):
            raise SecurityApiError("GoPlus has no security record for the token")
        return SecuritySnapshot(
            token_address=token,
            fetched_at=fetched_at,
            is_honeypot=_flag(raw.get("is_honeypot")),
            cannot_buy=_flag(raw.get("cannot_buy")),
            cannot_sell_all=_flag(raw.get("cannot_sell_all")),
            buy_tax_pct=_tax(raw.get("buy_tax")),
            sell_tax_pct=_tax(raw.get("sell_tax")),
            is_open_source=_flag(raw.get("is_open_source")),
            is_proxy=_flag(raw.get("is_proxy")),
            hidden_owner=_flag(raw.get("hidden_owner")),
            owner_change_balance=_flag(raw.get("owner_change_balance")),
            raw=json_safe(dict(raw)),
        )


def _flag(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value if value is not None else "").strip().lower()
    if text in {"1", "true"}:
        return True
    if text in {"0", "false"}:
        return False
    return None


def _tax(value: object) -> Decimal | None:
    try:
        fraction = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not fraction.is_finite() or fraction < 0:
        return None
    return fraction * 100
