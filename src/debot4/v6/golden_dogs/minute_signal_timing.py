"""Pure classification of timestamped evidence against 1m price crossings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .minute_breakout import MinuteWaveBoundary, PriceCrossing


class MinuteSignalStage(str, Enum):
    HISTORICAL = "historical"
    BEFORE_BASELINE = "before_baseline"
    STRICT_PRE_MOTION = "strict_pre_motion"
    MOTION_CANDLE_AMBIGUOUS = "motion_candle_ambiguous"
    EARLY_BEFORE_BREAKOUT = "early_before_breakout"
    BREAKOUT_CANDLE_AMBIGUOUS = "breakout_candle_ambiguous"
    AFTER_BREAKOUT = "after_breakout"
    BREAKOUT_NOT_OBSERVED = "breakout_not_observed"


@dataclass(frozen=True, slots=True)
class MinuteSignalTiming:
    occurred_at: int
    stage: MinuteSignalStage
    strict_advance: bool
    early_advance: bool
    seconds_to_motion_crossing: int | None
    seconds_to_breakout_crossing: int | None


def classify_minute_signal(
    occurred_at: int,
    boundary: MinuteWaveBoundary,
) -> MinuteSignalTiming:
    """Classify without pretending the intra-candle high order is known."""

    if occurred_at <= 0:
        raise ValueError("signal timestamp must be positive")
    motion = boundary.motion
    breakout = boundary.breakout
    if occurred_at < boundary.wave_start:
        stage = MinuteSignalStage.HISTORICAL
    elif occurred_at < boundary.baseline_established_at:
        stage = MinuteSignalStage.BEFORE_BASELINE
    elif motion is None:
        stage = MinuteSignalStage.STRICT_PRE_MOTION
    elif occurred_at < motion.crossing_before:
        stage = MinuteSignalStage.STRICT_PRE_MOTION
    elif occurred_at < motion.crossing_end_exclusive:
        stage = MinuteSignalStage.MOTION_CANDLE_AMBIGUOUS
    elif breakout is None:
        stage = MinuteSignalStage.BREAKOUT_NOT_OBSERVED
    elif occurred_at < breakout.crossing_before:
        stage = MinuteSignalStage.EARLY_BEFORE_BREAKOUT
    elif occurred_at < breakout.crossing_end_exclusive:
        stage = MinuteSignalStage.BREAKOUT_CANDLE_AMBIGUOUS
    else:
        stage = MinuteSignalStage.AFTER_BREAKOUT
    strict = stage in {
        MinuteSignalStage.HISTORICAL,
        MinuteSignalStage.STRICT_PRE_MOTION,
    }
    early = strict or stage == MinuteSignalStage.EARLY_BEFORE_BREAKOUT
    return MinuteSignalTiming(
        occurred_at=occurred_at,
        stage=stage,
        strict_advance=strict,
        early_advance=early,
        seconds_to_motion_crossing=_lead_seconds(occurred_at, motion),
        seconds_to_breakout_crossing=_lead_seconds(occurred_at, breakout),
    )


def _lead_seconds(at: int, crossing: PriceCrossing | None) -> int | None:
    return None if crossing is None else crossing.crossing_before - at
