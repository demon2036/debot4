"""Immutable values used by the DEX missed-opportunity audit."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class HttpAttempt:
    source: str
    method: str
    url: str
    request_json: str | None
    started_at_us: int
    completed_at_us: int
    latency_ms: int
    http_status: int | None
    response_bytes: int
    success: bool
    failure_reason: str | None


@dataclass(frozen=True, slots=True)
class JsonResponse:
    payload: Any | None
    attempt: HttpAttempt


@dataclass(frozen=True, slots=True)
class Gainer:
    token_address: str
    pair_address: str | None
    symbol: str
    name: str
    h1_change_pct: Decimal
    liquidity_usd: Decimal | None
    fdv_usd: Decimal | None
    market_cap_usd: Decimal | None
    price_usd: Decimal | None
    volume_h1_usd: Decimal | None
    txns_h1: int | None
    published_at_us: int | None = None


@dataclass(frozen=True, slots=True)
class Board:
    as_of_us: int
    source: str
    source_url: str
    universe: str
    ranking_exact: bool
    rows: tuple[Gainer, ...]
    attempts: tuple[HttpAttempt, ...]
    failure_reason: str | None = None

    @property
    def success(self) -> bool:
        return bool(self.rows)


@dataclass(frozen=True, slots=True)
class Coverage:
    token_address: str
    discovered: bool = False
    signal_id: str | None = None
    signal_at_us: int | None = None
    decided: bool = False
    decision_id: str | None = None
    decision_at_us: int | None = None
    decision_status: str | None = None
    bought: bool = False
    buy_id: str | None = None
    buy_at_us: int | None = None
    miss_reason: str = "not_discovered_by_debot"


@dataclass(frozen=True, slots=True)
class CoverageBatch:
    available: bool
    failure_reason: str | None
    rows: tuple[Coverage, ...]


@dataclass(frozen=True, slots=True)
class StoredRun:
    run_id: str
    as_of_us: int
    source: str
    row_count: int
    success: bool
