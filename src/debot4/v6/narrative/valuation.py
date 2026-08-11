"""Self-contained scenario valuation; deliberately no single target price."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math

from .domain import TokenRef, ValuationStatus
from .models import aware_utc


def _positive(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{name} must be positive and finite")
    return result


@dataclass(frozen=True, slots=True)
class ComparableAnchor:
    token: TokenRef
    label: str
    market_cap_usd: float
    as_of: datetime
    similarities: tuple[str, ...]
    differences: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", aware_utc(self.as_of, "comparable.as_of"))
        object.__setattr__(self, "market_cap_usd", _positive(self.market_cap_usd, "market_cap_usd"))
        if not self.label.strip() or not self.similarities:
            raise ValueError("comparable label and similarities are required")


@dataclass(frozen=True, slots=True)
class ValuationScenario:
    name: str
    low_usd: float
    high_usd: float
    rationale: str

    def __post_init__(self) -> None:
        low = _positive(self.low_usd, "scenario.low_usd")
        high = _positive(self.high_usd, "scenario.high_usd")
        if low > high:
            raise ValueError("scenario low cannot exceed high")
        if not self.name.strip() or not self.rationale.strip():
            raise ValueError("scenario name and rationale are required")
        object.__setattr__(self, "low_usd", low)
        object.__setattr__(self, "high_usd", high)


@dataclass(frozen=True, slots=True)
class ValuationView:
    as_of: datetime
    current_market_cap_usd: float
    status: ValuationStatus
    comparables: tuple[ComparableAnchor, ...] = ()
    scenarios: tuple[ValuationScenario, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", aware_utc(self.as_of, "valuation.as_of"))
        object.__setattr__(self, "current_market_cap_usd", _positive(self.current_market_cap_usd, "current_market_cap_usd"))
        object.__setattr__(self, "status", ValuationStatus(self.status))
        if any(item.as_of > self.as_of for item in self.comparables):
            raise ValueError("comparables cannot come from the future")
        if self.status is ValuationStatus.BOUNDED and (
            len(self.comparables) < 2 or len(self.scenarios) < 2
        ):
            raise ValueError("bounded valuation requires two comparables and scenarios")
