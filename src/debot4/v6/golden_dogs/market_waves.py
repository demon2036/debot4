"""Pure, provider-independent replay rules for completed market waves."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .models import Candle


MIN_WAVE_MULTIPLE = Decimal("2")
MIN_WAVE_PEAK_FDV_USD = Decimal("500000")
WAVE_RESET_FRACTION = Decimal("0.60")


@dataclass(frozen=True, slots=True)
class WavePhaseBounds:
    historical_start: int
    pre_trough_start: int
    trough_start: int
    peak_end_exclusive: int
    reset_end_exclusive: int
    window_end_exclusive: int

    def __post_init__(self) -> None:
        points = (
            self.historical_start,
            self.pre_trough_start,
            self.trough_start,
            self.peak_end_exclusive,
            self.reset_end_exclusive,
            self.window_end_exclusive,
        )
        if tuple(sorted(points)) != points:
            raise ValueError("wave-phase bounds are out of order")


def wave_phase_bounds(
    *,
    window_start: int,
    window_end_exclusive: int,
    trough_at: int,
    peak_at: int,
    reset_at: int,
    candle_seconds: int = 300,
    pre_trough_seconds: int = 1_800,
) -> WavePhaseBounds:
    """Return half-open evidence lanes around a completed candle wave."""

    if candle_seconds <= 0 or pre_trough_seconds < 0:
        raise ValueError("wave-phase durations are invalid")
    if not window_start <= trough_at <= peak_at <= reset_at < window_end_exclusive:
        raise ValueError("wave timestamps fall outside the research window")
    peak_end = min(peak_at + candle_seconds, window_end_exclusive)
    reset_end = min(reset_at + candle_seconds, window_end_exclusive)
    return WavePhaseBounds(
        historical_start=window_start,
        pre_trough_start=max(window_start, trough_at - pre_trough_seconds),
        trough_start=trough_at,
        peak_end_exclusive=peak_end,
        reset_end_exclusive=reset_end,
        window_end_exclusive=window_end_exclusive,
    )


@dataclass(frozen=True, slots=True)
class MarketWave:
    trough_at: int
    trough_price_usd: Decimal
    peak_at: int
    peak_close_price_usd: Decimal
    reset_at: int
    reset_close_price_usd: Decimal
    peak_fdv_usd: Decimal
    multiple: Decimal
    effective: bool

    def __post_init__(self) -> None:
        if not self.trough_at <= self.peak_at <= self.reset_at:
            raise ValueError("market-wave timestamps are out of order")
        prices = (
            self.trough_price_usd,
            self.peak_close_price_usd,
            self.reset_close_price_usd,
            self.peak_fdv_usd,
            self.multiple,
        )
        if min(prices) <= 0:
            raise ValueError("market-wave values must be positive")


@dataclass(frozen=True, slots=True)
class MarketWaveReplay:
    completed_swings: tuple[MarketWave, ...]
    ath_at: int | None
    ath_high_price_usd: Decimal | None
    ath_fdv_usd: Decimal | None

    @property
    def effective_waves(self) -> tuple[MarketWave, ...]:
        return tuple(wave for wave in self.completed_swings if wave.effective)

    @property
    def filtered_swing_count(self) -> int:
        return sum(not wave.effective for wave in self.completed_swings)


def replay_market_waves(
    candles: Iterable[Candle],
    total_supply: Decimal,
    *,
    minimum_multiple: Decimal = MIN_WAVE_MULTIPLE,
    minimum_peak_fdv_usd: Decimal = MIN_WAVE_PEAK_FDV_USD,
    reset_fraction: Decimal = WAVE_RESET_FRACTION,
) -> MarketWaveReplay:
    """Replay completed close-to-close swings inside an already bounded window.

    The first traded candle's open is the launch trough. Later troughs and all
    peaks use closes. A swing forms at ``minimum_multiple`` and completes only
    after a close at or below ``reset_fraction`` of its best close. Completed
    sub-threshold swings reset state but are not effective waves.
    """

    if total_supply <= 0:
        raise ValueError("total supply must be positive")
    if minimum_multiple <= 1 or minimum_peak_fdv_usd <= 0:
        raise ValueError("wave thresholds are invalid")
    if not 0 < reset_fraction < 1:
        raise ValueError("reset fraction must be between zero and one")

    traded = tuple(
        sorted(
            (bar for bar in candles if bar.open > 0 and bar.close > 0),
            key=lambda bar: bar.time,
        )
    )
    if not traded:
        return MarketWaveReplay((), None, None, None)

    ath = max(traded, key=lambda bar: (bar.high, -bar.time))
    trough_at = traded[0].time
    trough = traded[0].open
    peak_at = trough_at
    peak = trough
    formed = False
    completed: list[MarketWave] = []

    for bar in traded:
        close = bar.close
        if not formed and close < trough:
            trough_at, trough = bar.time, close
            peak_at, peak = bar.time, close
        elif close > peak:
            peak_at, peak = bar.time, close

        formed = formed or peak >= trough * minimum_multiple
        if formed and close <= peak * reset_fraction:
            peak_fdv = peak * total_supply
            completed.append(MarketWave(
                trough_at=trough_at,
                trough_price_usd=trough,
                peak_at=peak_at,
                peak_close_price_usd=peak,
                reset_at=bar.time,
                reset_close_price_usd=close,
                peak_fdv_usd=peak_fdv,
                multiple=peak / trough,
                effective=peak_fdv >= minimum_peak_fdv_usd,
            ))
            trough_at, trough = bar.time, close
            peak_at, peak = bar.time, close
            formed = False

    return MarketWaveReplay(
        completed_swings=tuple(completed),
        ath_at=ath.time,
        ath_high_price_usd=ath.high,
        ath_fdv_usd=ath.high * total_supply,
    )
