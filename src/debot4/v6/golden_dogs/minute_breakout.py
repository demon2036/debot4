"""Pure one-minute price-stage boundaries for a replayed market wave."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .models import Candle


PRICE_MOTION_MULTIPLE = Decimal("1.20")
MAIN_BREAKOUT_MULTIPLE = Decimal("2")


@dataclass(frozen=True, slots=True)
class PriceCrossing:
    """Earliest minute whose high proves that a threshold was crossed."""

    multiple: Decimal
    threshold_price_usd: Decimal
    crossing_bar_at: int
    crossing_before: int
    crossing_end_exclusive: int
    first_close_confirmed_at: int | None

    def __post_init__(self) -> None:
        if self.multiple <= 1 or self.threshold_price_usd <= 0:
            raise ValueError("invalid price crossing threshold")
        if not (
            self.crossing_bar_at == self.crossing_before
            < self.crossing_end_exclusive
        ):
            raise ValueError("invalid price crossing interval")
        if (
            self.first_close_confirmed_at is not None
            and self.first_close_confirmed_at < self.crossing_end_exclusive
        ):
            raise ValueError("close confirmation predates high crossing")


@dataclass(frozen=True, slots=True)
class MinuteWaveBoundary:
    """Auditable one-minute boundaries inside one retrospective 5m wave."""

    wave_start: int
    trough_end_exclusive: int
    wave_end_exclusive: int
    interval_seconds: int
    candle_count: int
    baseline_price_usd: Decimal
    baseline_fdv_usd: Decimal
    baseline_bar_at: int
    baseline_established_at: int
    baseline_source: str
    motion: PriceCrossing | None
    breakout: PriceCrossing | None
    peak_high_at: int
    peak_high_price_usd: Decimal

    def __post_init__(self) -> None:
        if not (
            0 < self.wave_start < self.trough_end_exclusive
            <= self.wave_end_exclusive
        ):
            raise ValueError("invalid minute-wave bounds")
        if self.interval_seconds <= 0 or self.candle_count <= 0:
            raise ValueError("invalid minute-wave candle metadata")
        if min(
            self.baseline_price_usd,
            self.baseline_fdv_usd,
            self.peak_high_price_usd,
        ) <= 0:
            raise ValueError("minute-wave prices must be positive")
        if self.baseline_source not in {"open", "close"}:
            raise ValueError("invalid minute-wave baseline source")


def analyze_minute_wave(
    candles: Iterable[Candle],
    total_supply: Decimal,
    *,
    wave_start: int,
    trough_end_exclusive: int,
    wave_end_exclusive: int,
    interval_seconds: int = 60,
    motion_multiple: Decimal = PRICE_MOTION_MULTIPLE,
    breakout_multiple: Decimal = MAIN_BREAKOUT_MULTIPLE,
) -> MinuteWaveBoundary:
    """Locate conservative pre-motion and pre-2x deadlines.

    The supplied wave and trough window come from a completed 5m replay. The
    baseline is the lowest observable open/close in that trough window. A high
    crossing only proves that the threshold happened somewhere in that minute;
    therefore only evidence strictly before ``crossing_before`` is guaranteed
    to predate it. Evidence inside the crossing candle remains ambiguous.
    """

    if total_supply <= 0:
        raise ValueError("total supply must be positive")
    if not 0 < wave_start < trough_end_exclusive <= wave_end_exclusive:
        raise ValueError("invalid minute-wave bounds")
    if interval_seconds <= 0:
        raise ValueError("minute interval must be positive")
    if not 1 < motion_multiple < breakout_multiple:
        raise ValueError("price-stage multiples are invalid")

    bars = tuple(sorted(
        (
            bar for bar in candles
            if wave_start <= bar.time < wave_end_exclusive
            and bar.open > 0 and bar.close > 0 and bar.high > 0
        ),
        key=lambda bar: bar.time,
    ))
    if not bars:
        raise ValueError("minute wave has no priced candles")
    trough_bars = tuple(bar for bar in bars if bar.time < trough_end_exclusive)
    if not trough_bars:
        trough_bars = (bars[0],)

    candidates: list[tuple[Decimal, int, int, str]] = []
    for bar in trough_bars:
        candidates.append((bar.open, bar.time, bar.time, "open"))
        candidates.append((
            bar.close, bar.time + interval_seconds, bar.time, "close",
        ))
    baseline, established_at, baseline_bar_at, source = min(candidates)
    eligible = tuple(bar for bar in bars if bar.time >= established_at)
    if source == "open":
        eligible = tuple(bar for bar in bars if bar.time >= baseline_bar_at)

    motion = _crossing(
        eligible, baseline, motion_multiple, interval_seconds,
    )
    breakout = _crossing(
        eligible, baseline, breakout_multiple, interval_seconds,
    )
    peak = max(bars, key=lambda bar: (bar.high, -bar.time))
    return MinuteWaveBoundary(
        wave_start=wave_start,
        trough_end_exclusive=trough_end_exclusive,
        wave_end_exclusive=wave_end_exclusive,
        interval_seconds=interval_seconds,
        candle_count=len(bars),
        baseline_price_usd=baseline,
        baseline_fdv_usd=baseline * total_supply,
        baseline_bar_at=baseline_bar_at,
        baseline_established_at=established_at,
        baseline_source=source,
        motion=motion,
        breakout=breakout,
        peak_high_at=peak.time,
        peak_high_price_usd=peak.high,
    )


def _crossing(
    bars: tuple[Candle, ...],
    baseline: Decimal,
    multiple: Decimal,
    interval_seconds: int,
) -> PriceCrossing | None:
    threshold = baseline * multiple
    crossed = next((bar for bar in bars if bar.high >= threshold), None)
    if crossed is None:
        return None
    confirmed = next(
        (bar.time + interval_seconds for bar in bars if bar.close >= threshold),
        None,
    )
    return PriceCrossing(
        multiple=multiple,
        threshold_price_usd=threshold,
        crossing_bar_at=crossed.time,
        crossing_before=crossed.time,
        crossing_end_exclusive=crossed.time + interval_seconds,
        first_close_confirmed_at=confirmed,
    )
