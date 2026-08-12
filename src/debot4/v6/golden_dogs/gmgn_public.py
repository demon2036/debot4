"""Anonymous GMGN adapter for provider-tagged token trades and token risk data."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Mapping
from urllib.parse import urlencode

import httpx

from .gmgn_http import GmgnPublicTransport
from .models import EvidenceReceipt, normalize_evm_address


TRADES_PATH = "/vas/api/v1/token_trades"
INFO_PATH = "/mrwapi/v1/multi_token_full_info"
_TX_HASH = re.compile(r"0x[0-9a-f]{64}")


class PublicGmgnError(RuntimeError):
    """Sanitized public endpoint transport or schema failure."""


@dataclass(frozen=True, slots=True)
class GmgnTaggedTrade:
    wallet: str
    token_address: str
    event: str
    timestamp: int
    token_amount: Decimal
    amount_usd: Decimal
    price_usd: Decimal
    transaction_hash: str
    name: str
    x_handle: str | None
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GmgnTradePage:
    trades: tuple[GmgnTaggedTrade, ...]
    next_cursor: str | None
    receipt: EvidenceReceipt
    oldest_row_at: int | None = None


@dataclass(frozen=True, slots=True)
class GmgnRiskSnapshot:
    token_address: str
    creator_address: str | None
    creator_from_address: str | None
    creator_fund_from: str | None
    creator_fund_tx_hash: str | None
    creator_transfer_at: int | None
    top_ten_holder_rate: Decimal | None
    dev_team_hold_rate: Decimal | None
    creator_hold_rate: Decimal | None
    rug: bool | None
    rug_ratio: Decimal | None
    security: Mapping[str, Any]
    receipt: EvidenceReceipt


class PublicGmgnClient:
    def __init__(self, *, timeout_seconds: float = 30, attempts: int = 3,
                 client: httpx.Client | None = None) -> None:
        if timeout_seconds <= 0 or not 1 <= attempts <= 5:
            raise ValueError("invalid GMGN client bounds")
        self._transport = GmgnPublicTransport(
            timeout_seconds=timeout_seconds, attempts=attempts, client=client,
        )

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> "PublicGmgnClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def fetch_kol_trades(self, chain: str, token: str, *, limit: int = 100,
                         cursor: str | None = None) -> GmgnTradePage:
        if chain != "bsc" or not 1 <= limit <= 100:
            raise ValueError("invalid GMGN KOL-trade query")
        token = normalize_evm_address(token)
        params = {"limit": str(limit), "tag": "kol"}
        if cursor:
            params["cursor"] = cursor
        path = f"{TRADES_PATH}/{chain}/{token}?{urlencode(params)}"
        payload, receipt = self._transport.request_json("GET", path)
        data = _object(payload.get("data"), "trade data")
        rows = data.get("history")
        if (
            not isinstance(rows, list) or len(rows) > limit
            or any(not isinstance(row, Mapping) for row in rows)
        ):
            raise PublicGmgnError("GMGN trade history has invalid schema")
        trades = tuple(
            trade for row in rows if (trade := _parse_trade(row, token)) is not None
        )
        row_times = tuple(_required_timestamp(row.get("timestamp")) for row in rows)
        cursor_value = str(data.get("next") or "").strip() or None
        if cursor_value and len(cursor_value) > 2048:
            raise PublicGmgnError("GMGN trade cursor exceeds the limit")
        return GmgnTradePage(
            trades, cursor_value, receipt, min(row_times) if row_times else None,
        )

    def fetch_risk(self, chain: str, token: str) -> GmgnRiskSnapshot:
        if chain != "bsc":
            raise ValueError("invalid GMGN risk query")
        token = normalize_evm_address(token)
        body = {"chain": chain, "addresses": [token]}
        payload, receipt = self._transport.request_json("POST", INFO_PATH, body=body)
        rows = payload.get("data")
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], Mapping):
            raise PublicGmgnError("GMGN token risk data has invalid schema")
        row = rows[0]
        creator = _address_or_none(row.get("creator_address"))
        creator_stat = row.get("creator_stat")
        creator_stat = creator_stat if isinstance(creator_stat, Mapping) else {}
        security = row.get("security")
        return GmgnRiskSnapshot(
            token_address=token,
            creator_address=creator,
            creator_from_address=_address_or_none(creator_stat.get("from_address")),
            creator_fund_from=_address_or_none(creator_stat.get("fund_from")),
            creator_fund_tx_hash=_tx_hash_or_none(creator_stat.get("fund_tx_hash")),
            creator_transfer_at=_integer(creator_stat.get("transfer_ts")),
            top_ten_holder_rate=_decimal(row.get("top_10_holder_rate")),
            dev_team_hold_rate=_decimal(row.get("dev_team_hold_rate")),
            creator_hold_rate=_decimal(row.get("creator_hold_rate")),
            rug=_boolean(row.get("rug")),
            rug_ratio=_decimal(row.get("rug_ratio")),
            security=dict(security) if isinstance(security, Mapping) else {},
            receipt=receipt,
        )


def _parse_trade(row: Mapping[str, Any], token: str) -> GmgnTaggedTrade | None:
    wallet = normalize_evm_address(str(row.get("maker") or ""))
    row_token = normalize_evm_address(str(row.get("token_address") or ""))
    tx_hash = str(row.get("tx_hash") or "").strip().casefold()
    event = str(row.get("event") or "").strip().casefold()
    timestamp = _required_timestamp(row.get("timestamp"))
    tags = tuple(str(item).strip().casefold() for item in row.get("maker_tags", []) if str(item).strip())
    if row_token != token or event not in {
        "buy", "sell", "add", "remove", "transferin", "transferout", "burn",
    }:
        raise PublicGmgnError("GMGN trade identity is invalid")
    if not _TX_HASH.fullmatch(tx_hash):
        raise PublicGmgnError("GMGN trade locator is invalid")
    if "kol" not in tags:
        raise PublicGmgnError("GMGN tag filter returned a non-KOL row")
    if event not in {"buy", "sell"}:
        return None
    return GmgnTaggedTrade(
        wallet, token, event, timestamp,
        _required_decimal(row.get("base_amount")),
        _required_decimal(row.get("amount_usd")),
        _required_decimal(row.get("price_usd")),
        tx_hash,
        str(row.get("maker_name") or "").strip(),
        str(row.get("maker_twitter_username") or "").strip().lstrip("@") or None,
        tags,
    )


def _object(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicGmgnError(f"GMGN {label} is not an object")
    return value


def _decimal(value: object) -> Decimal | None:
    try:
        number = Decimal(str(value)) if value not in {None, ""} else None
    except InvalidOperation as exc:
        raise PublicGmgnError("GMGN contains an invalid number") from exc
    return number if number is None or number.is_finite() else None


def _required_decimal(value: object) -> Decimal:
    number = _decimal(value)
    if number is None or number <= 0:
        raise PublicGmgnError("GMGN trade amount must be positive")
    return number


def _integer(value: object) -> int | None:
    number = _decimal(value)
    return int(number) if number is not None and number == number.to_integral() else None


def _required_timestamp(value: object) -> int:
    timestamp = _integer(value)
    if timestamp is None or timestamp <= 0:
        raise PublicGmgnError("GMGN trade timestamp is invalid")
    return timestamp


def _boolean(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _address_or_none(value: object) -> str | None:
    try:
        return normalize_evm_address(str(value or ""))
    except ValueError:
        return None


def _tx_hash_or_none(value: object) -> str | None:
    tx_hash = str(value or "").strip().casefold()
    return tx_hash if _TX_HASH.fullmatch(tx_hash) else None
