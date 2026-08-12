"""Anonymous GMGN adapter for wallet identity, risk and frozen rank evidence."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
from urllib.parse import urlencode

import httpx

from .gmgn_http import GmgnPublicTransport
from .models import EvidenceReceipt, normalize_evm_address


@dataclass(frozen=True, slots=True)
class GmgnWalletProfile:
    wallet: str
    name: str
    x_handle: str | None
    public_x_handle: str | None
    stat_x_handle: str | None
    x_bound: bool | None
    x_fans: int | None
    tags: tuple[str, ...]
    risk: Mapping[str, Any]
    fund_from: str | None
    fund_tx_hash: str | None
    fetched_at: int
    receipts: tuple[EvidenceReceipt, ...]


@dataclass(frozen=True, slots=True)
class GmgnKolRankRow:
    wallet: str
    name: str
    x_handle: str | None
    tags: tuple[str, ...]
    winrate_7d: Decimal | None
    transactions_7d: int
    buys_7d: int
    sells_7d: int
    realized_profit_7d: Decimal | None


@dataclass(frozen=True, slots=True)
class GmgnKolRankSnapshot:
    rows: tuple[GmgnKolRankRow, ...]
    ordered_by: str
    fetched_at: int
    receipt: EvidenceReceipt


class PublicGmgnWalletClient:
    def __init__(self, *, timeout_seconds: float = 30, attempts: int = 3,
                 client: httpx.Client | None = None) -> None:
        self._transport = GmgnPublicTransport(
            timeout_seconds=timeout_seconds, attempts=attempts, client=client,
        )

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> "PublicGmgnWalletClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def fetch_profile(self, chain: str, wallet: str) -> GmgnWalletProfile:
        if chain != "bsc":
            raise ValueError("invalid GMGN wallet-profile chain")
        wallet = normalize_evm_address(wallet)
        public, public_receipt = self._transport.request_json(
            "GET", f"/defi/quotation/v1/smartmoney/{chain}/walletNew/{wallet}",
        )
        stat, stat_receipt = self._transport.request_json(
            "GET", f"/api/v1/wallet_stat/{chain}/{wallet}/7d",
        )
        public_data = _object(public.get("data"), "wallet profile")
        stat_data = _object(stat.get("data"), "wallet statistics")
        public_handle = _handle(public_data.get("twitter_username"))
        stat_handle = _handle(stat_data.get("twitter_username"))
        handles = {public_handle, stat_handle} - {None}
        x_handle = next(iter(handles)) if len(handles) == 1 else None
        tags = _tags(public_data.get("tags")) | _tags(stat_data.get("tags"))
        risk = stat_data.get("risk") or public_data.get("risk")
        return GmgnWalletProfile(
            wallet=wallet,
            name=str(stat_data.get("name") or public_data.get("name") or "").strip(),
            x_handle=x_handle,
            public_x_handle=public_handle,
            stat_x_handle=stat_handle,
            x_bound=_combined_binding(
                public_data.get("twitter_bind"), stat_data.get("twitter_bind"),
            ),
            x_fans=_integer(stat_data.get("twitter_fans_num") or public_data.get("twitter_fans_num")),
            tags=tuple(sorted(tags)),
            risk=dict(risk) if isinstance(risk, Mapping) else {},
            fund_from=_address_or_none(stat_data.get("fund_from")),
            fund_tx_hash=_text_or_none(stat_data.get("fund_tx_hash")),
            fetched_at=max(public_receipt.fetched_at, stat_receipt.fetched_at),
            receipts=(public_receipt, stat_receipt),
        )

    def fetch_kol_rank(self, chain: str = "bsc") -> GmgnKolRankSnapshot:
        if chain != "bsc":
            raise ValueError("invalid GMGN KOL-rank chain")
        ordered_by = "winrate_7d"
        query = urlencode({
            "tag": "kol", "orderby": ordered_by, "direction": "desc",
        })
        payload, receipt = self._transport.request_json(
            "GET", f"/api/v1/rank/{chain}/wallets/7d?{query}",
        )
        rank = _object(payload.get("data"), "wallet rank").get("rank")
        if not isinstance(rank, list) or len(rank) > 100:
            raise ValueError("GMGN wallet rank has invalid schema")
        rows = tuple(_parse_rank(item) for item in rank if isinstance(item, Mapping))
        return GmgnKolRankSnapshot(rows, ordered_by, receipt.fetched_at, receipt)


def _parse_rank(row: Mapping[str, Any]) -> GmgnKolRankRow:
    wallet = normalize_evm_address(str(row.get("wallet_address") or row.get("address") or ""))
    return GmgnKolRankRow(
        wallet=wallet,
        name=str(row.get("name") or row.get("nickname") or "").strip(),
        x_handle=_handle(row.get("twitter_username")),
        tags=tuple(sorted(_tags(row.get("tags")))),
        winrate_7d=_decimal(row.get("winrate_7d")),
        transactions_7d=_integer(row.get("txs_7d")) or 0,
        buys_7d=_integer(row.get("buy_7d")) or 0,
        sells_7d=_integer(row.get("sell_7d")) or 0,
        realized_profit_7d=_decimal(row.get("realized_profit_7d")),
    )


def _object(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"GMGN {label} is not an object")
    return value


def _tags(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item).strip().casefold() for item in value if str(item).strip()}


def _handle(value: object) -> str | None:
    return str(value or "").strip().lstrip("@") or None


def _decimal(value: object) -> Decimal | None:
    try:
        number = Decimal(str(value)) if value not in {None, ""} else None
    except InvalidOperation as exc:
        raise ValueError("GMGN wallet data contains an invalid number") from exc
    return number if number is None or number.is_finite() else None


def _integer(value: object) -> int | None:
    number = _decimal(value)
    return int(number) if number is not None and number == number.to_integral() else None


def _boolean(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _combined_binding(*values: object) -> bool | None:
    known = tuple(item for item in values if isinstance(item, bool))
    if False in known:
        return False
    return True if True in known else None


def _address_or_none(value: object) -> str | None:
    try:
        return normalize_evm_address(str(value or ""))
    except ValueError:
        return None


def _text_or_none(value: object) -> str | None:
    return str(value or "").strip().casefold() or None
