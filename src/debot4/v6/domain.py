"""Small immutable records shared by the independent v6 pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class WalletTrade:
    alias: str
    wallet: str | None
    traded_at: datetime
    volume_usd: Decimal
    token_amount: Decimal


@dataclass(frozen=True, slots=True)
class DeBotSignal:
    signal_id: str
    token_address: str
    signal_kind: str
    group_name: str
    event_at: datetime
    available_at: datetime
    channel_id: str
    pair_address: str | None
    dex_name: str | None
    token_name: str | None
    token_symbol: str | None
    token_decimals: int | None
    total_supply: Decimal | None
    created_at: datetime | None
    provider_fdv_usd: Decimal | None
    provider_liquidity_usd: Decimal | None
    narrative_urls: tuple[str, ...]
    description: str | None
    wallet_trades: tuple[WalletTrade, ...]
    kol_buy_qualified: bool
    kol_buy_reason: str
    security_hint: Mapping[str, Any] = field(default_factory=dict)
    raw_context: Mapping[str, Any] = field(default_factory=dict)

    @property
    def evidence_uri(self) -> str:
        return f"https://debot.ai/token/bsc/{self.token_address}"


@dataclass(frozen=True, slots=True)
class SecuritySnapshot:
    token_address: str
    fetched_at: datetime
    is_honeypot: bool | None
    cannot_buy: bool | None
    cannot_sell_all: bool | None
    buy_tax_pct: Decimal | None
    sell_tax_pct: Decimal | None
    is_open_source: bool | None
    is_proxy: bool | None
    hidden_owner: bool | None
    owner_change_balance: bool | None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChainHead:
    number: int
    block_hash: str
    parent_hash: str
    timestamp: datetime
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class PairState:
    head: ChainHead
    pair_address: str
    token_address: str
    quote_address: str
    token_is_zero: bool
    token_decimals: int
    quote_decimals: int
    token_reserve_raw: int
    quote_reserve_raw: int
    total_supply_raw: int
    quote_usd: Decimal


@dataclass(frozen=True, slots=True)
class ExecutionQuote:
    state: PairState
    notional_usd: Decimal
    buy_tax_pct: Decimal
    sell_tax_pct: Decimal
    spot_fdv_usd: Decimal
    fill_fdv_usd: Decimal
    liquidity_usd: Decimal
    price_impact_bps: Decimal
    tokens_received_raw: int
    immediate_exit_usd: Decimal


@dataclass(frozen=True, slots=True)
class PositionMark:
    state: PairState
    fdv_usd: Decimal
    exit_value_usd: Decimal


@dataclass(frozen=True, slots=True)
class GateResult:
    passed: bool
    reason: str
    details: Mapping[str, Any] = field(default_factory=dict)
