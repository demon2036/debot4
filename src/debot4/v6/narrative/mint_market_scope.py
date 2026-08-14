"""Pure freshness scope for retrospective new-mint market audits."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..dex_audit.models import Gainer
from ..identity import bsc_address, utc_datetime
from .market_signal import MarketAnomaly


RECENT_MINT_WINDOW = timedelta(hours=2)
PUBLISH_TIME_SKEW = timedelta(seconds=30)


@dataclass(frozen=True, slots=True)
class MintMarketScopeExclusion:
    exact_ca: str
    reason: str
    published_at: datetime | None

    def as_public_dict(self) -> dict[str, str | None]:
        return {
            "exact_ca": self.exact_ca,
            "reason": self.reason,
            "published_at": (
                None if self.published_at is None else self.published_at.isoformat()
            ),
        }


@dataclass(frozen=True, slots=True)
class MintMarketScope:
    eligible: tuple[MarketAnomaly, ...]
    exclusions: tuple[MintMarketScopeExclusion, ...]
    effective_start: datetime
    recent_window: timedelta
    clock_skew: timedelta

    def as_public_dict(self) -> dict[str, object]:
        return {
            "quality_candidates": len(self.eligible) + len(self.exclusions),
            "eligible": len(self.eligible),
            "excluded": len(self.exclusions),
            "effective_start": self.effective_start.isoformat(),
            "recent_window_seconds": int(self.recent_window.total_seconds()),
            "clock_skew_seconds": int(self.clock_skew.total_seconds()),
            "exclusions": [item.as_public_dict() for item in self.exclusions],
        }


def scope_recent_mint_candidates(
    anomalies: tuple[MarketAnomaly, ...],
    gainers: tuple[Gainer, ...],
    *,
    now: datetime,
    policy_started_at: datetime,
    recent_window: timedelta = RECENT_MINT_WINDOW,
    clock_skew: timedelta = PUBLISH_TIME_SKEW,
) -> MintMarketScope:
    """Keep only freshly published tokens that this alert policy could observe."""

    if recent_window <= timedelta(0) or clock_skew < timedelta(0):
        raise ValueError("mint market scope intervals are invalid")
    current = utc_datetime(now)
    policy_start = utc_datetime(policy_started_at)
    recent_start = current - recent_window
    policy_floor = policy_start - clock_skew
    effective_start = max(recent_start, policy_floor)
    rows: dict[str, Gainer] = {}
    for item in gainers:
        try:
            rows[bsc_address(item.token_address)] = item
        except ValueError:
            continue
    eligible: list[MarketAnomaly] = []
    excluded: list[MintMarketScopeExclusion] = []
    for anomaly in anomalies:
        row = rows.get(anomaly.exact_ca)
        published_at, reason = _published_at(None if row is None else row.published_at_us)
        if reason is None and published_at is not None:
            reason = _freshness_reason(
                published_at,
                current=current,
                policy_floor=policy_floor,
                recent_start=recent_start,
                clock_skew=clock_skew,
            )
        if reason is None:
            eligible.append(anomaly)
        else:
            excluded.append(MintMarketScopeExclusion(
                anomaly.exact_ca, reason, published_at
            ))
    return MintMarketScope(
        tuple(eligible), tuple(excluded), effective_start, recent_window, clock_skew
    )


def _published_at(value: int | None) -> tuple[datetime | None, str | None]:
    if value is None:
        return None, "published_at_missing"
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None, "published_at_invalid"
    try:
        return datetime.fromtimestamp(value / 1_000_000, timezone.utc), None
    except (OverflowError, OSError, ValueError):
        return None, "published_at_invalid"


def _freshness_reason(
    published_at: datetime,
    *,
    current: datetime,
    policy_floor: datetime,
    recent_start: datetime,
    clock_skew: timedelta,
) -> str | None:
    if published_at > current + clock_skew:
        return "published_at_in_future"
    if published_at < policy_floor:
        return "published_before_policy_start"
    if published_at < recent_start:
        return "published_before_recent_window"
    return None


__all__ = [
    "MintMarketScope",
    "MintMarketScopeExclusion",
    "PUBLISH_TIME_SKEW",
    "RECENT_MINT_WINDOW",
    "scope_recent_mint_candidates",
]
