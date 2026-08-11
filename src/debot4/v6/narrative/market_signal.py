"""Pure quality gate for exact BSC one-hour market anomalies."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from ..dex_audit.models import Board, Gainer
from ..identity import bsc_address, stable_id, utc_datetime


DEFAULT_STAGES = tuple(
    Decimal(value) for value in ("3", "5", "10", "20", "50", "100", "250", "500", "1000")
)


@dataclass(frozen=True, slots=True)
class MarketAnomaly:
    """An exact-CA market trigger; it is neither evidence nor a buy signal."""

    exact_ca: str
    observed_at: datetime
    symbol: str
    name: str
    h1_change_pct: Decimal
    liquidity_usd: Decimal
    valuation_usd: Decimal
    volume_h1_usd: Decimal
    txns_h1: int
    stage_pct: Decimal
    source: str
    source_url: str
    anomaly_id: str = field(init=False)

    def __post_init__(self) -> None:
        exact_ca = bsc_address(self.exact_ca)
        observed_at = utc_datetime(self.observed_at)
        symbol = self.symbol.strip()[:80]
        name = self.name.strip()[:160]
        source = self.source.strip()[:80]
        source_url = self.source_url.strip()[:500]
        decimals = (
            self.h1_change_pct,
            self.liquidity_usd,
            self.valuation_usd,
            self.volume_h1_usd,
            self.stage_pct,
        )
        if any(not item.is_finite() or item < 0 for item in decimals):
            raise ValueError("market anomaly decimals must be finite and non-negative")
        if self.stage_pct <= 0 or self.h1_change_pct < self.stage_pct:
            raise ValueError("market anomaly stage must be positive and reached")
        if type(self.txns_h1) is not int or self.txns_h1 < 0:
            raise ValueError("market anomaly transactions must be non-negative")
        if not source or not source_url:
            raise ValueError("market anomaly source is required")
        identity_day = observed_at.date().isoformat()
        object.__setattr__(self, "exact_ca", exact_ca)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "source_url", source_url)
        object.__setattr__(
            self,
            "anomaly_id",
            stable_id(
                "market-anomaly", source, exact_ca, identity_day,
                format(self.stage_pct, "f"),
            ),
        )

    def describe(self) -> str:
        ratio = self.valuation_usd / self.liquidity_usd
        return (
            f"BSC exact 1h gainer: {self.symbol or self.name or 'unknown'}; "
            f"change={self.h1_change_pct}% stage={self.stage_pct}%; "
            f"liquidity=${self.liquidity_usd}; valuation=${self.valuation_usd}; "
            f"valuation/liquidity={ratio:.2f}; volume1h=${self.volume_h1_usd}; "
            f"txns1h={self.txns_h1}. Investigate why it is moving now."
        )


@dataclass(frozen=True, slots=True)
class MarketRejection:
    exact_ca: str
    reason: str


@dataclass(frozen=True, slots=True)
class MarketSelection:
    anomalies: tuple[MarketAnomaly, ...]
    rejections: tuple[MarketRejection, ...]


@dataclass(frozen=True, slots=True)
class MarketQualityPolicy:
    """Reject mechanically impressive but economically unusable rankings."""

    min_change_pct: Decimal = Decimal("3")
    min_liquidity_usd: Decimal = Decimal("25000")
    min_volume_h1_usd: Decimal = Decimal("5000")
    min_txns_h1: int = 4
    max_valuation_liquidity_ratio: Decimal = Decimal("500")
    min_volume_liquidity_ratio: Decimal = Decimal("0.05")
    max_anomalies: int = 10
    stages: tuple[Decimal, ...] = DEFAULT_STAGES

    def __post_init__(self) -> None:
        values = (
            self.min_change_pct,
            self.min_liquidity_usd,
            self.min_volume_h1_usd,
            self.max_valuation_liquidity_ratio,
            self.min_volume_liquidity_ratio,
        )
        if any(not item.is_finite() or item < 0 for item in values):
            raise ValueError("market quality bounds must be finite and non-negative")
        if type(self.min_txns_h1) is not int or self.min_txns_h1 < 0:
            raise ValueError("minimum transaction count is invalid")
        if type(self.max_anomalies) is not int or not 1 <= self.max_anomalies <= 100:
            raise ValueError("max_anomalies must be between 1 and 100")
        if not self.stages or tuple(sorted(set(self.stages))) != self.stages:
            raise ValueError("market stages must be unique and increasing")
        if any(not item.is_finite() or item <= 0 for item in self.stages):
            raise ValueError("market stages must be finite and positive")
        if self.min_change_pct < self.stages[0]:
            raise ValueError("minimum change cannot be below the first stage")

    def select(self, board: Board) -> MarketSelection:
        if not board.ranking_exact or board.source != "coinmarketcap_datahub":
            return MarketSelection((), (MarketRejection("", "board_not_exact"),))
        observed_at = datetime.fromtimestamp(
            board.as_of_us / 1_000_000, timezone.utc
        )
        accepted: list[MarketAnomaly] = []
        rejected: list[MarketRejection] = []
        for row in board.rows:
            anomaly, reason = self._qualify(row, observed_at, board)
            if anomaly is None:
                rejected.append(MarketRejection(row.token_address, reason))
            elif len(accepted) < self.max_anomalies:
                accepted.append(anomaly)
        return MarketSelection(tuple(accepted), tuple(rejected))

    def _qualify(
        self, row: Gainer, observed_at: datetime, board: Board
    ) -> tuple[MarketAnomaly | None, str]:
        valuation = row.market_cap_usd or row.fdv_usd
        if row.h1_change_pct < self.min_change_pct:
            return None, "change_below_threshold"
        if row.liquidity_usd is None or row.liquidity_usd < self.min_liquidity_usd:
            return None, "liquidity_below_threshold"
        if valuation is None or valuation <= 0:
            return None, "valuation_missing"
        if valuation / row.liquidity_usd > self.max_valuation_liquidity_ratio:
            return None, "valuation_liquidity_ratio_too_high"
        if row.volume_h1_usd is None or row.volume_h1_usd < self.min_volume_h1_usd:
            return None, "volume_below_threshold"
        if row.volume_h1_usd / row.liquidity_usd < self.min_volume_liquidity_ratio:
            return None, "volume_liquidity_ratio_too_low"
        if row.txns_h1 is None or row.txns_h1 < self.min_txns_h1:
            return None, "transactions_below_threshold"
        stage = max(item for item in self.stages if item <= row.h1_change_pct)
        return MarketAnomaly(
            row.token_address,
            observed_at,
            row.symbol,
            row.name,
            row.h1_change_pct,
            row.liquidity_usd,
            valuation,
            row.volume_h1_usd,
            row.txns_h1,
            stage,
            board.source,
            board.source_url,
        ), "accepted"
