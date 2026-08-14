"""Anonymous GMGN adapter for unfiltered token-trade evidence."""

from __future__ import annotations

from dataclasses import dataclass
import base64
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Mapping
from urllib.parse import urlencode

import httpx

from .gmgn_http import GmgnPublicTransport
from .models import EvidenceReceipt, normalize_evm_address


TRADES_PATH = "/vas/api/v1/token_trades"
SUPPORTED_EVENTS = frozenset({
    "buy", "sell", "add", "remove", "transferin", "transferout", "burn", "launch",
})
_TX_HASH = re.compile(r"0x[0-9a-f]{64}")


class GmgnMarketTradeError(RuntimeError):
    """Sanitized unfiltered trade transport or schema failure."""


@dataclass(frozen=True, slots=True)
class GmgnMarketTrade:
    wallet: str
    token_address: str
    event: str
    timestamp: int
    token_amount: Decimal | None
    amount_usd: Decimal | None
    price_usd: Decimal | None
    transaction_hash: str
    name: str
    x_handle: str | None
    wallet_tags: tuple[str, ...]
    token_tags: tuple[str, ...]
    event_tags: tuple[str, ...]
    provider_sequence: int | None = None


@dataclass(frozen=True, slots=True)
class GmgnMarketTradePage:
    trades: tuple[GmgnMarketTrade, ...]
    next_cursor: str | None
    receipt: EvidenceReceipt
    oldest_row_at: int | None


class PublicGmgnMarketTradeClient:
    def __init__(self, *, timeout_seconds: float = 30, attempts: int = 3,
                 client: httpx.Client | None = None) -> None:
        if timeout_seconds <= 0 or not 1 <= attempts <= 5:
            raise ValueError("invalid GMGN market-trade client bounds")
        self._transport = GmgnPublicTransport(
            timeout_seconds=timeout_seconds, attempts=attempts, client=client,
        )

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> "PublicGmgnMarketTradeClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def fetch_page(
        self, chain: str, token: str, *, end_at: int | None = None,
        cursor: str | None = None, limit: int = 50,
    ) -> GmgnMarketTradePage:
        if chain != "bsc" or not 1 <= limit <= 50:
            raise ValueError("invalid GMGN market-trade query")
        if end_at is not None and end_at <= 0:
            raise ValueError("GMGN market-trade end time must be positive")
        if cursor and end_at is not None:
            raise ValueError("GMGN page accepts either end time or cursor")
        token = normalize_evm_address(token)
        params = {"limit": str(limit)}
        if end_at is not None:
            params["to"] = str(end_at)
        if cursor:
            params["cursor"] = cursor
        path = f"{TRADES_PATH}/{chain}/{token}?{urlencode(params)}"
        payload, receipt = self._transport.request_json("GET", path)
        data = _object(payload.get("data"), "trade data")
        raw = data.get("history")
        if (
            not isinstance(raw, list) or len(raw) > 50
            or any(not isinstance(row, Mapping) for row in raw)
        ):
            raise GmgnMarketTradeError("GMGN market trades have invalid schema")
        trades = tuple(_parse_trade(row, token) for row in raw)
        next_cursor = str(data.get("next") or "").strip() or None
        if next_cursor and len(next_cursor) > 2_048:
            raise GmgnMarketTradeError("GMGN market-trade cursor exceeds the limit")
        oldest = min((trade.timestamp for trade in trades), default=None)
        return GmgnMarketTradePage(trades, next_cursor, receipt, oldest)


def _parse_trade(row: Mapping[str, Any], token: str) -> GmgnMarketTrade:
    try:
        wallet = normalize_evm_address(str(row.get("maker") or ""))
        row_token = normalize_evm_address(str(row.get("token_address") or ""))
    except ValueError as exc:
        raise GmgnMarketTradeError("GMGN market-trade identity is invalid") from exc
    event = str(row.get("event") or "").strip().casefold()
    tx_hash = str(row.get("tx_hash") or "").strip().casefold()
    timestamp = _positive_integer(row.get("timestamp"))
    if row_token != token or event not in SUPPORTED_EVENTS:
        raise GmgnMarketTradeError("GMGN market-trade identity is invalid")
    if not _TX_HASH.fullmatch(tx_hash) or timestamp is None:
        raise GmgnMarketTradeError("GMGN market-trade locator is invalid")
    token_amount = _number(row.get("base_amount"))
    amount_usd = _number(row.get("amount_usd"))
    price_usd = _number(row.get("price_usd"))
    missing_priced_swap = event in {"buy", "sell"} and (
        token_amount is None or amount_usd is None or price_usd is None
        or min(token_amount, amount_usd, price_usd) <= 0
    )
    if event == "buy" and missing_priced_swap:
        raise GmgnMarketTradeError("GMGN buy values must be positive")
    if event == "sell" and missing_priced_swap:
        token_amount = amount_usd = price_usd = None
    return GmgnMarketTrade(
        wallet=wallet, token_address=token, event=event, timestamp=timestamp,
        token_amount=token_amount, amount_usd=amount_usd, price_usd=price_usd,
        transaction_hash=tx_hash,
        name=str(row.get("maker_name") or "").strip(),
        x_handle=str(row.get("maker_twitter_username") or "").strip().lstrip("@") or None,
        wallet_tags=_tags(row.get("maker_tags")),
        token_tags=_tags(row.get("maker_token_tags")),
        event_tags=_tags(row.get("maker_event_tags")),
        provider_sequence=_provider_sequence(row.get("id")),
    )


def _object(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GmgnMarketTradeError(f"GMGN {label} is not an object")
    return value


def _number(value: object) -> Decimal | None:
    try:
        result = Decimal(str(value)) if value not in {None, ""} else None
    except InvalidOperation as exc:
        raise GmgnMarketTradeError("GMGN market trade contains an invalid number") from exc
    if result is not None and (not result.is_finite() or result < 0):
        raise GmgnMarketTradeError("GMGN market trade contains an invalid number")
    return result


def _positive_integer(value: object) -> int | None:
    number = _number(value)
    return (
        int(number) if number is not None and number > 0
        and number == number.to_integral() else None
    )


def _tags(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise GmgnMarketTradeError("GMGN market-trade tags have invalid schema")
    return tuple(sorted({
        str(item).strip().casefold() for item in value if str(item).strip()
    }))


def _provider_sequence(value: object) -> int | None:
    """Decode GMGN's opaque base64 decimal order without assigning chain meaning."""

    text = str(value or "").strip()
    if not text:
        return None
    if len(text) > 128:
        raise GmgnMarketTradeError("GMGN market-trade sequence exceeds the limit")
    try:
        raw = base64.b64decode(text, validate=True).decode("ascii")
    except (ValueError, UnicodeDecodeError) as exc:
        raise GmgnMarketTradeError("GMGN market-trade sequence is invalid") from exc
    if not raw.isdecimal() or len(raw) > 30:
        raise GmgnMarketTradeError("GMGN market-trade sequence is invalid")
    sequence = int(raw)
    if sequence <= 0:
        raise GmgnMarketTradeError("GMGN market-trade sequence is invalid")
    return sequence
