"""Pure, causally safe market trajectory measured from one X post."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .models import Candle


@dataclass(frozen=True, slots=True)
class XPostMarketTrajectory:
    post_at: int
    reference_at: int
    reference_open_price_usd: Decimal
    reference_fdv_usd: Decimal
    peak_at: int
    peak_fdv_usd: Decimal
    post_to_peak_multiple: Decimal
    seconds_to_peak: int
    reference_age_seconds: int
    precision: str = "last_1m_open_at_or_before_post_vs_window_5m_high"


def assess_x_post_market(
    candles: tuple[Candle, ...],
    *,
    total_supply: Decimal,
    post_at: int,
    peak_at: int,
    peak_fdv_usd: Decimal,
    max_reference_age_seconds: int = 300,
) -> XPostMarketTrajectory:
    """Use only a candle open already known when the post was published."""

    if min(total_supply, peak_fdv_usd) <= 0:
        raise ValueError("market supply and peak FDV must be positive")
    if post_at <= 0 or peak_at <= post_at:
        raise ValueError("X post must precede the measured market peak")
    if max_reference_age_seconds < 0:
        raise ValueError("reference age bound cannot be negative")
    eligible = tuple(bar for bar in candles if bar.time <= post_at and bar.open > 0)
    if not eligible:
        raise ValueError("no causal market candle exists at or before the X post")
    reference = max(eligible, key=lambda bar: bar.time)
    age = post_at - reference.time
    if age > max_reference_age_seconds:
        raise ValueError("market reference before X post is too stale")
    fdv = reference.open * total_supply
    if fdv <= 0:
        raise ValueError("X post market reference FDV is invalid")
    return XPostMarketTrajectory(
        post_at=post_at,
        reference_at=reference.time,
        reference_open_price_usd=reference.open,
        reference_fdv_usd=fdv,
        peak_at=peak_at,
        peak_fdv_usd=peak_fdv_usd,
        post_to_peak_multiple=peak_fdv_usd / fdv,
        seconds_to_peak=peak_at - post_at,
        reference_age_seconds=age,
    )
