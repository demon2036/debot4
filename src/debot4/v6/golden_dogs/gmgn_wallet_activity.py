"""Bounded GMGN wallet-activity adapter for selectivity denominators."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
from urllib.parse import urlencode

import httpx

from .gmgn_http import GmgnPublicTransport
from .models import EvidenceReceipt, normalize_evm_address


@dataclass(frozen=True, slots=True)
class GmgnWalletActivity:
    wallet: str
    token_address: str
    event: str
    timestamp: int
    transaction_hash: str
    price_usd: Decimal | None = None
    token_total_supply: Decimal | None = None


@dataclass(frozen=True, slots=True)
class GmgnWalletActivityHistory:
    activities: tuple[GmgnWalletActivity, ...]
    receipts: tuple[EvidenceReceipt, ...]
    coverage_complete: bool
    stop_reason: str


class PublicGmgnWalletActivityClient:
    def __init__(self, *, timeout_seconds: float = 30, attempts: int = 3,
                 client: httpx.Client | None = None) -> None:
        self._transport = GmgnPublicTransport(
            timeout_seconds=timeout_seconds, attempts=attempts, client=client,
        )

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> "PublicGmgnWalletActivityClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def fetch_history(
        self, wallet: str, start: int, end_exclusive: int, *, max_pages: int = 100,
    ) -> GmgnWalletActivityHistory:
        wallet = normalize_evm_address(wallet)
        if not 0 < start < end_exclusive or not 1 <= max_pages <= 200:
            raise ValueError("invalid wallet-activity bounds")
        rows: dict[tuple[str, str, str], GmgnWalletActivity] = {}
        receipts: list[EvidenceReceipt] = []
        cursor: str | None = None
        seen: set[str] = set()
        complete, reason = False, "page_limit"
        for _ in range(max_pages):
            page, next_cursor, receipt = self._fetch_page(wallet, cursor)
            receipts.append(receipt)
            for item in page:
                if start <= item.timestamp < end_exclusive:
                    key = (item.transaction_hash, item.event, item.token_address)
                    rows[key] = item
            if not next_cursor:
                complete, reason = True, "provider_history_exhausted"
                break
            if page and min(item.timestamp for item in page) < start:
                complete, reason = True, "crossed_period_start"
                break
            if next_cursor in seen:
                reason = "cursor_loop"
                break
            seen.add(next_cursor)
            cursor = next_cursor
        return GmgnWalletActivityHistory(
            tuple(sorted(rows.values(), key=lambda item: item.timestamp)),
            tuple(receipts), complete, reason,
        )

    def _fetch_page(
        self, wallet: str, cursor: str | None,
    ) -> tuple[tuple[GmgnWalletActivity, ...], str | None, EvidenceReceipt]:
        params = {"wallet": wallet, "limit": "50", "cost": "10"}
        if cursor:
            params["cursor"] = cursor
        payload, receipt = self._transport.request_json(
            "GET", f"/vas/api/v1/wallet_activity/bsc?{urlencode(params)}",
        )
        data = payload.get("data")
        if not isinstance(data, Mapping) or not isinstance(data.get("activities"), list):
            raise ValueError("GMGN wallet activity has invalid schema")
        raw = data["activities"]
        if len(raw) > 50 or any(not isinstance(item, Mapping) for item in raw):
            raise ValueError("GMGN wallet activity page exceeds bounds")
        rows = tuple(_parse(item, wallet) for item in raw)
        next_cursor = str(data.get("next") or "").strip() or None
        if next_cursor and len(next_cursor) > 2_048:
            raise ValueError("GMGN wallet activity cursor exceeds bounds")
        return rows, next_cursor, receipt


def _parse(row: Mapping[str, Any], wallet: str) -> GmgnWalletActivity:
    token = row.get("token")
    if not isinstance(token, Mapping):
        raise ValueError("GMGN wallet activity token is missing")
    observed = normalize_evm_address(str(row.get("wallet") or ""))
    address = normalize_evm_address(str(token.get("address") or ""))
    event = str(row.get("event_type") or "").strip().casefold()
    timestamp = row.get("timestamp")
    transaction = str(row.get("tx_hash") or "").strip().casefold()
    price_usd = _number(row.get("price_usd"))
    total_supply = _number(token.get("total_supply"))
    supported = {"buy", "sell", "add", "remove", "transferin", "transferout", "burn"}
    if observed != wallet or event not in supported:
        raise ValueError("GMGN wallet activity identity is invalid")
    if not isinstance(timestamp, int) or timestamp <= 0 or not _transaction(transaction):
        raise ValueError("GMGN wallet activity locator is invalid")
    return GmgnWalletActivity(
        wallet, address, event, timestamp, transaction,
        price_usd, total_supply,
    )


def _transaction(value: str) -> bool:
    return len(value) == 66 and value.startswith("0x") and all(
        item in "0123456789abcdef" for item in value[2:]
    )


def _number(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool) or str(value).strip() == "":
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("GMGN wallet activity contains an invalid number") from exc
    if not number.is_finite() or number < 0:
        raise ValueError("GMGN wallet activity contains an invalid number")
    return number
