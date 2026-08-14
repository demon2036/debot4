"""Immutable values exposed by the mint-alert audit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ..identity import bsc_address, utc_datetime
from .market_signal import MarketAnomaly
from .mint_alert import MintAlert
from .mint_market_scope import MintMarketScope
from .mint_location import DEBOT_STAGE_SOURCES


AUDIT_CAVEATS = (
    "h1_market_lead_is_not_fixed_window_golden_dog_proof",
    "current_board_absence_cannot_prove_a_false_positive",
    "final_golden_dog_qualification_remains_in_golden_dogs",
)


@dataclass(frozen=True, slots=True)
class StoredMintAlert:
    alert: MintAlert
    delivered_at: datetime | None

    def __post_init__(self) -> None:
        if self.delivered_at is not None:
            object.__setattr__(self, "delivered_at", utc_datetime(self.delivered_at))


@dataclass(frozen=True, slots=True)
class DeBotMintSeen:
    exact_ca: str
    first_observed_at: datetime
    last_observed_at: datetime
    sources: tuple[str, ...]

    def __post_init__(self) -> None:
        first = utc_datetime(self.first_observed_at)
        last = utc_datetime(self.last_observed_at)
        sources = tuple(sorted(set(self.sources)))
        if last < first or not sources:
            raise ValueError("invalid DeBot mint observation window")
        allowed = frozenset(DEBOT_STAGE_SOURCES.values())
        if any(source not in allowed for source in sources):
            raise ValueError("non-DeBot source entered the mint alert audit")
        object.__setattr__(self, "exact_ca", bsc_address(self.exact_ca))
        object.__setattr__(self, "first_observed_at", first)
        object.__setattr__(self, "last_observed_at", last)
        object.__setattr__(self, "sources", sources)


@dataclass(frozen=True, slots=True)
class AuditViolation:
    code: str
    subject: str
    detail: str

    def as_public_dict(self) -> dict[str, str]:
        return {"code": self.code, "subject": self.subject, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class MarketCoverageRow:
    anomaly: MarketAnomaly
    coverage: str
    debot: DeBotMintSeen | None
    gate_outcome: str | None
    gate_reason: str | None
    alert: StoredMintAlert | None

    def as_public_dict(self) -> dict[str, object]:
        item = self.anomaly
        return {
            "exact_ca": item.exact_ca,
            "symbol": item.symbol,
            "name": item.name,
            "h1_change_pct": _number(item.h1_change_pct),
            "liquidity_usd": _number(item.liquidity_usd),
            "valuation_usd": _number(item.valuation_usd),
            "volume_h1_usd": _number(item.volume_h1_usd),
            "txns_h1": item.txns_h1,
            "quality_stage_pct": _number(item.stage_pct),
            "coverage": self.coverage,
            "debot_sources": [] if self.debot is None else list(self.debot.sources),
            "debot_first_observed_at": _time(
                None if self.debot is None else self.debot.first_observed_at
            ),
            "gate_outcome": self.gate_outcome,
            "gate_reason": self.gate_reason,
            "alert_id": None if self.alert is None else self.alert.alert.alert_id,
        }


@dataclass(frozen=True, slots=True)
class MintAlertAuditReport:
    as_of: datetime
    policy_started_at: datetime
    gate_groups: int
    alerts: int
    debot_exact_cas: int
    market_source: str
    market_available: bool
    market_failure_reason: str | None
    market_scope: MintMarketScope
    violations: tuple[AuditViolation, ...]
    market_leads: tuple[MarketCoverageRow, ...]

    @property
    def healthy(self) -> bool:
        return self.market_available and not self.violations

    @property
    def review_required(self) -> bool:
        return any(item.coverage != "alerted" for item in self.market_leads)

    @property
    def attention_required(self) -> bool:
        return not self.healthy or self.review_required

    def as_public_dict(self) -> dict[str, object]:
        return {
            "schema": "debot4.v6.mint-alert-audit.v1",
            "status": "attention" if self.attention_required else "ok",
            "as_of": self.as_of.isoformat(),
            "policy_started_at": self.policy_started_at.isoformat(),
            "gate_groups": self.gate_groups,
            "alerts": self.alerts,
            "debot_exact_cas": self.debot_exact_cas,
            "market_source": self.market_source,
            "market_available": self.market_available,
            "market_failure_reason": self.market_failure_reason,
            "market_scope": self.market_scope.as_public_dict(),
            "review_required": self.review_required,
            "violations": [item.as_public_dict() for item in self.violations],
            "market_leads": [item.as_public_dict() for item in self.market_leads],
            "caveats": list(AUDIT_CAVEATS),
        }


def _number(value: Decimal) -> str:
    return format(value, "f")


def _time(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


__all__ = [
    "AUDIT_CAVEATS",
    "AuditViolation",
    "DeBotMintSeen",
    "MarketCoverageRow",
    "MintAlertAuditReport",
    "StoredMintAlert",
]
