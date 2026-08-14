from decimal import Decimal

import pytest

from debot4.v6.golden_dogs.minute_breakout import analyze_minute_wave
from debot4.v6.golden_dogs.models import Candle


def bar(
    at: int, open_: str, high: str, close: str, *, low: str = "1",
) -> Candle:
    return Candle(
        at, Decimal(open_), Decimal(high), Decimal(low), Decimal(close),
        Decimal("1"),
    )


def test_boundaries_use_trough_then_first_high_crossing_minute() -> None:
    candles = (
        bar(100, "10", "20", "9"),
        bar(160, "9", "9", "8"),
        bar(220, "8", "9", "8.8"),
        bar(280, "8.8", "10", "9.8"),
        bar(340, "9.8", "17", "16.5"),
    )
    result = analyze_minute_wave(
        candles, Decimal("1000"), wave_start=100,
        trough_end_exclusive=280, wave_end_exclusive=400,
    )

    assert result.baseline_price_usd == Decimal("8")
    assert result.baseline_established_at == 220
    assert result.baseline_fdv_usd == Decimal("8000")
    assert result.motion is not None
    assert result.motion.crossing_before == 280
    assert result.motion.crossing_end_exclusive == 340
    assert result.motion.first_close_confirmed_at == 340
    assert result.breakout is not None
    assert result.breakout.crossing_before == 340
    assert result.breakout.first_close_confirmed_at == 400


def test_pre_baseline_spike_is_not_misclassified_as_wave_crossing() -> None:
    candles = (
        bar(100, "10", "30", "9"),
        bar(160, "9", "9", "8"),
        bar(220, "8", "9", "8.5"),
    )
    result = analyze_minute_wave(
        candles, Decimal("10"), wave_start=100,
        trough_end_exclusive=220, wave_end_exclusive=280,
    )

    assert result.motion is None
    assert result.breakout is None


def test_open_baseline_can_cross_inside_the_same_minute() -> None:
    result = analyze_minute_wave(
        (bar(100, "5", "11", "10"),), Decimal("10"),
        wave_start=100, trough_end_exclusive=160, wave_end_exclusive=160,
    )

    assert result.baseline_source == "open"
    assert result.baseline_established_at == 100
    assert result.breakout is not None
    assert result.breakout.crossing_before == 100


def test_invalid_or_empty_inputs_fail_closed() -> None:
    with pytest.raises(ValueError, match="no priced candles"):
        analyze_minute_wave(
            (), Decimal("1"), wave_start=100,
            trough_end_exclusive=160, wave_end_exclusive=220,
        )
    with pytest.raises(ValueError, match="multiples"):
        analyze_minute_wave(
            (bar(100, "1", "2", "2"),), Decimal("1"), wave_start=100,
            trough_end_exclusive=160, wave_end_exclusive=220,
            motion_multiple=Decimal("2"), breakout_multiple=Decimal("2"),
        )
