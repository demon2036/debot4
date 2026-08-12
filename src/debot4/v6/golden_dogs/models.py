"""Immutable research records shared through small explicit interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re


_EVM_ADDRESS = re.compile(r"0x[0-9a-f]{40}")


def normalize_evm_address(value: str) -> str:
    address = value.strip().casefold()
    if not _EVM_ADDRESS.fullmatch(address):
        raise ValueError("value must be an exact EVM address")
    return address


@dataclass(frozen=True, slots=True)
class TokenSeed:
    chain: str
    address: str
    name: str
    symbol: str
    launchpad: str
    created_at: int
    creator_address: str | None
    rank_supply: Decimal | None
    current_kols: int
    max_kols: int
    social_urls: tuple[str, ...]
    discovered_sources: tuple[str, ...]

    def __post_init__(self) -> None:
        chain = self.chain.strip().casefold()
        address = normalize_evm_address(self.address)
        if chain not in {"bsc", "robinhood"}:
            raise ValueError("unsupported golden-dog chain")
        if self.created_at <= 0 or min(self.current_kols, self.max_kols) < 0:
            raise ValueError("invalid token seed values")
        if self.rank_supply is not None and self.rank_supply <= 0:
            raise ValueError("rank supply must be positive")
        object.__setattr__(self, "chain", chain)
        object.__setattr__(self, "address", address)
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "symbol", self.symbol.strip())
        object.__setattr__(self, "launchpad", self.launchpad.strip().casefold())
        object.__setattr__(self, "social_urls", tuple(dict.fromkeys(self.social_urls)))
        object.__setattr__(
            self, "discovered_sources", tuple(sorted(set(self.discovered_sources))),
        )


@dataclass(frozen=True, slots=True)
class Candle:
    time: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def __post_init__(self) -> None:
        if self.time <= 0 or min(self.open, self.high, self.low, self.close) < 0:
            raise ValueError("invalid market candle")
        if self.volume < 0 or self.high < self.low:
            raise ValueError("invalid market candle range")


@dataclass(frozen=True, slots=True)
class EvidenceReceipt:
    kind: str
    url: str
    fetched_at: int
    sha256: str
    request_sha256: str | None = None
    request_context: str | None = None

    def __post_init__(self) -> None:
        if not self.kind or not self.url.startswith("https://"):
            raise ValueError("invalid evidence receipt")
        if self.fetched_at <= 0 or not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("invalid evidence receipt fingerprint")
        has_hash = self.request_sha256 is not None
        has_context = self.request_context is not None
        if has_hash != has_context:
            raise ValueError("request evidence must include both context and fingerprint")
        if has_hash and not re.fullmatch(r"[0-9a-f]{64}", self.request_sha256 or ""):
            raise ValueError("invalid request evidence fingerprint")
        if has_context and not (self.request_context or "").strip():
            raise ValueError("request evidence context cannot be empty")


@dataclass(frozen=True, slots=True)
class MarketTrace:
    candles: tuple[Candle, ...]
    total_supply: Decimal | None
    decimals: int | None
    receipt: EvidenceReceipt

    def __post_init__(self) -> None:
        if self.total_supply is not None and self.total_supply <= 0:
            raise ValueError("market trace supply must be positive")
        if self.decimals is not None and not 0 <= self.decimals <= 36:
            raise ValueError("market trace decimals are invalid")
        object.__setattr__(self, "candles", tuple(sorted(self.candles, key=lambda x: x.time)))


@dataclass(frozen=True, slots=True)
class Observation:
    chain: str
    address: str
    name: str
    symbol: str
    launchpad: str
    created_at: int
    window_start: int
    window_end_exclusive: int
    first_trade_at: int | None
    first_price_usd: Decimal | None
    peak_at: int | None
    peak_price_usd: Decimal | None
    total_supply: Decimal | None
    supply_source: str | None
    initial_fdv_usd: Decimal | None
    approx_peak_fdv_usd: Decimal | None
    peak_multiple: Decimal | None
    tiers: tuple[str, ...]
    meets_peak_threshold: bool
    current_kols: int
    max_kols: int
    precision: str
    status: str
    receipts: tuple[EvidenceReceipt, ...]

    def __post_init__(self) -> None:
        if not 0 < self.window_start < self.window_end_exclusive:
            raise ValueError("market window bounds are invalid")
        if self.window_end_exclusive - self.window_start > 7 * 86_400:
            raise ValueError("market window cannot exceed seven days")
        if not self.window_start <= self.created_at < self.window_end_exclusive:
            raise ValueError("token creation must fall inside its market window")
        for timestamp in (self.first_trade_at, self.peak_at):
            if timestamp is not None and not self.window_start <= timestamp < self.window_end_exclusive:
                raise ValueError("market observation timestamp is outside its window")
        if self.meets_peak_threshold and self.status != "complete":
            raise ValueError("incomplete market evidence cannot meet the peak threshold")
        object.__setattr__(self, "receipts", tuple(self.receipts))
