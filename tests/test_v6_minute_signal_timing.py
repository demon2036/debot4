from decimal import Decimal

from debot4.v6.golden_dogs.minute_breakout import analyze_minute_wave
from debot4.v6.golden_dogs.minute_signal_timing import (
    MinuteSignalStage,
    classify_minute_signal,
)
from debot4.v6.golden_dogs.models import Candle


def boundary():
    candles = (
        Candle(100, Decimal("10"), Decimal("10"), Decimal("9"),
               Decimal("9"), Decimal("1")),
        Candle(160, Decimal("9"), Decimal("12"), Decimal("9"),
               Decimal("11"), Decimal("1")),
        Candle(220, Decimal("11"), Decimal("19"), Decimal("11"),
               Decimal("18"), Decimal("1")),
    )
    return analyze_minute_wave(
        candles, Decimal("1"), wave_start=100,
        trough_end_exclusive=160, wave_end_exclusive=280,
    )


def test_conservative_price_stages_are_half_open() -> None:
    expected = {
        99: MinuteSignalStage.HISTORICAL,
        100: MinuteSignalStage.BEFORE_BASELINE,
        159: MinuteSignalStage.BEFORE_BASELINE,
        160: MinuteSignalStage.MOTION_CANDLE_AMBIGUOUS,
        219: MinuteSignalStage.MOTION_CANDLE_AMBIGUOUS,
        220: MinuteSignalStage.BREAKOUT_CANDLE_AMBIGUOUS,
        279: MinuteSignalStage.BREAKOUT_CANDLE_AMBIGUOUS,
        280: MinuteSignalStage.AFTER_BREAKOUT,
    }
    for at, stage in expected.items():
        assert classify_minute_signal(at, boundary()).stage == stage


def test_only_unambiguous_pre_crossing_stages_count_as_advance() -> None:
    earlier = classify_minute_signal(99, boundary())
    inside = classify_minute_signal(170, boundary())
    assert earlier.strict_advance and earlier.early_advance
    assert not inside.strict_advance and not inside.early_advance
    assert earlier.seconds_to_motion_crossing == 61
