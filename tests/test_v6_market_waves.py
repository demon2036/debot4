from __future__ import annotations

from decimal import Decimal

import pytest

from debot4.v6.golden_dogs.market_waves import (
    replay_market_waves,
    wave_phase_bounds,
)
from debot4.v6.golden_dogs.models import Candle


SUPPLY = Decimal("1000000")


def bar(at: int, open_: str, high: str, close: str) -> Candle:
    low = min(Decimal(open_), Decimal(close))
    return Candle(
        at,
        Decimal(open_),
        Decimal(high),
        low,
        Decimal(close),
        Decimal("1"),
    )


def test_first_traded_open_is_launch_trough_and_high_is_only_ath() -> None:
    replay = replay_market_waves((
        bar(10, "0.01", "1.20", "0.60"),
        bar(20, "0.60", "1.00", "1.00"),
        bar(30, "1.00", "1.00", "0.60"),
    ), SUPPLY)

    wave, = replay.effective_waves
    assert wave.trough_at == 10
    assert wave.trough_price_usd == Decimal("0.01")
    assert wave.peak_at == 20
    assert wave.peak_close_price_usd == Decimal("1.00")
    assert wave.multiple == Decimal("100")
    assert replay.ath_at == 10
    assert replay.ath_fdv_usd == Decimal("1200000.00")


def test_subthreshold_swing_resets_before_later_effective_wave() -> None:
    replay = replay_market_waves((
        bar(10, "0.10", "0.25", "0.20"),
        bar(20, "0.20", "0.22", "0.11"),
        bar(30, "0.11", "0.70", "0.60"),
        bar(40, "0.60", "0.60", "0.36"),
    ), SUPPLY)

    assert replay.filtered_swing_count == 1
    effective, = replay.effective_waves
    assert effective.trough_at == 20
    assert effective.peak_at == 30
    assert effective.reset_at == 40


def test_close_must_reach_reset_boundary_to_complete_wave() -> None:
    replay = replay_market_waves((
        bar(10, "0.20", "0.60", "0.60"),
        bar(20, "0.60", "0.60", "0.361"),
    ), SUPPLY)
    assert replay.completed_swings == ()

    completed = replay_market_waves((
        bar(10, "0.20", "0.60", "0.60"),
        bar(20, "0.60", "0.60", "0.360"),
    ), SUPPLY)
    assert len(completed.completed_swings) == 1


def test_new_close_low_replaces_unformed_trough() -> None:
    replay = replay_market_waves((
        bar(10, "0.40", "0.70", "0.60"),
        bar(20, "0.60", "0.60", "0.30"),
        bar(30, "0.30", "0.80", "0.70"),
        bar(40, "0.70", "0.70", "0.40"),
    ), SUPPLY)
    wave, = replay.effective_waves
    assert wave.trough_at == 20
    assert wave.multiple == Decimal("0.70") / Decimal("0.30")


@pytest.mark.parametrize("supply", [Decimal("0"), Decimal("-1")])
def test_supply_must_be_positive(supply: Decimal) -> None:
    with pytest.raises(ValueError, match="total supply"):
        replay_market_waves((), supply)


def test_wave_phase_bounds_use_half_open_peak_and_reset_candles() -> None:
    phases = wave_phase_bounds(
        window_start=100,
        window_end_exclusive=2_000,
        trough_at=500,
        peak_at=800,
        reset_at=1_100,
        candle_seconds=300,
        pre_trough_seconds=1_800,
    )

    assert phases.historical_start == phases.pre_trough_start == 100
    assert phases.trough_start == 500
    assert phases.peak_end_exclusive == 1_100
    assert phases.reset_end_exclusive == 1_400


def test_wave_phase_bounds_reject_invalid_window_or_duration() -> None:
    with pytest.raises(ValueError, match="outside"):
        wave_phase_bounds(
            window_start=100, window_end_exclusive=1_000,
            trough_at=90, peak_at=200, reset_at=300,
        )
    with pytest.raises(ValueError, match="durations"):
        wave_phase_bounds(
            window_start=100, window_end_exclusive=1_000,
            trough_at=200, peak_at=300, reset_at=400,
            candle_seconds=0,
        )
