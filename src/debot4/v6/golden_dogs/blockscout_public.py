"""Read-only Blockscout token discovery with bounded, receipted pagination."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import time
from typing import Any, Mapping

import httpx

from .models import EvidenceReceipt


BASE_URL = "https://robinhoodchain.blockscout.com"
TOKENS_PATH = "/api/v2/tokens"


class PublicBlockscoutError(RuntimeError):
    """Sanitized Blockscout transport or schema failure."""


@dataclass(frozen=True, slots=True)
class TokenIndexRow:
    address: str
    name: str
    symbol: str
    circulating_market_cap_usd: Decimal | None
    holders_count: int


@dataclass(frozen=True, slots=True)
class TokenIndexPage:
    rows: tuple[TokenIndexRow, ...]
    next_page_params: Mapping[str, object] | None
    receipt: EvidenceReceipt


class RobinhoodBlockscoutClient:
    def __init__(self, *, timeout_seconds: float = 30, attempts: int = 3) -> None:
        if timeout_seconds <= 0 or not 1 <= attempts <= 5:
            raise ValueError("invalid Blockscout bounds")
        self.attempts = attempts
        self._client = httpx.Client(
            base_url=BASE_URL,
            timeout=timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            headers={"Accept": "application/json", "User-Agent": "DeBot4EvidenceResearch/1.0"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "RobinhoodBlockscoutClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def fetch_token_page(
        self, next_page_params: Mapping[str, object] | None = None,
    ) -> TokenIndexPage:
        params: dict[str, object] = {"type": "ERC-20"}
        params.update(next_page_params or {})
        payload, receipt = self._json(params)
        items = payload.get("items")
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise PublicBlockscoutError("Blockscout token rows have invalid schema")
        next_params = payload.get("next_page_params")
        if next_params is not None and not isinstance(next_params, dict):
            raise PublicBlockscoutError("Blockscout pagination has invalid schema")
        return TokenIndexPage(
            tuple(_parse_row(item) for item in items),
            next_params,
            receipt,
        )

    def _json(self, params: Mapping[str, object]) -> tuple[dict[str, Any], EvidenceReceipt]:
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                response = self._client.get(TOKENS_PATH, params=params)
                if response.status_code != 200:
                    raise PublicBlockscoutError(
                        f"Blockscout public API returned HTTP {response.status_code}"
                    )
                raw = response.content
                if len(raw) > 8_000_000:
                    raise PublicBlockscoutError("Blockscout response exceeded byte limit")
                payload = response.json()
                if not isinstance(payload, dict):
                    raise PublicBlockscoutError("Blockscout response is not an object")
                return payload, EvidenceReceipt(
                    kind="robinhood_blockscout_json",
                    url=str(response.url),
                    fetched_at=int(time.time()),
                    sha256=hashlib.sha256(raw).hexdigest(),
                )
            except (httpx.HTTPError, json.JSONDecodeError, PublicBlockscoutError) as exc:
                last_error = exc
                if attempt + 1 < self.attempts:
                    time.sleep(0.25 * (2**attempt))
        raise PublicBlockscoutError("Blockscout public API request failed") from last_error


def _parse_row(item: Mapping[str, Any]) -> TokenIndexRow:
    address = str(item.get("address_hash") or "").strip().casefold()
    if len(address) != 42 or not address.startswith("0x"):
        raise PublicBlockscoutError("Blockscout token row lacks an exact CA")
    return TokenIndexRow(
        address=address,
        name=str(item.get("name") or "").strip(),
        symbol=str(item.get("symbol") or "").strip(),
        circulating_market_cap_usd=_decimal(item.get("circulating_market_cap")),
        holders_count=_integer(item.get("holders_count")) or 0,
    )


def _decimal(value: object) -> Decimal | None:
    try:
        number = Decimal(str(value)) if value not in {None, ""} else None
    except InvalidOperation as exc:
        raise PublicBlockscoutError("Blockscout contains an invalid number") from exc
    return number if number is None or number.is_finite() else None


def _integer(value: object) -> int | None:
    number = _decimal(value)
    return int(number) if number is not None and number == number.to_integral() else None
