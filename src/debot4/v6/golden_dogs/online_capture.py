"""Pure gates separating advance prediction from early motion detection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class CaptureKind(str, Enum):
    EXOGENOUS_ADVANCE = "exogenous_advance"
    ONCHAIN_ADVANCE_CANDIDATE = "onchain_advance_candidate"
    EARLY_MOTION = "early_motion"
    NOT_ACTIONABLE = "not_actionable"


@dataclass(frozen=True, slots=True)
class CaptureAssessment:
    kind: CaptureKind
    actionable: bool
    alert_at: int | None
    seconds_to_motion: int | None
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CaptureLaneCoverage:
    public_advance: bool
    fresh_public_advance: bool
    provider_timing_ceiling: bool
    qualified_provider_advance: bool
    timing_union_ceiling: bool
    semantic_public_or_qualified_provider_advance: bool
    early_motion_detection: bool


def assess_exogenous_signal(
    occurred_at: int,
    first_seen_at: int,
    motion_at: int,
    *,
    semantically_qualified: bool,
    exact_ca_bound: bool,
) -> CaptureAssessment:
    """Count a public signal only when it was actually seen before motion."""

    if min(occurred_at, first_seen_at, motion_at) <= 0:
        raise ValueError("capture times must be positive")
    if first_seen_at < occurred_at:
        raise ValueError("first seen cannot precede occurrence")
    reasons = []
    if not semantically_qualified:
        reasons.append("semantic_gate_failed")
    if not exact_ca_bound:
        reasons.append("exact_ca_unresolved")
    if first_seen_at >= motion_at:
        reasons.append("not_seen_before_motion")
    actionable = not reasons
    return CaptureAssessment(
        kind=(CaptureKind.EXOGENOUS_ADVANCE if actionable
              else CaptureKind.NOT_ACTIONABLE),
        actionable=actionable,
        alert_at=first_seen_at if actionable else None,
        seconds_to_motion=motion_at - first_seen_at,
        reasons=tuple(reasons) or ("qualified_public_advance_signal",),
    )


def assess_onchain_candidate(
    signal_at: int,
    confirmed_at: int,
    motion_at: int,
    *,
    prior_block: bool,
    observation_latency_seconds: int,
    as_of_qualified: bool,
) -> CaptureAssessment:
    """Apply confirmation, observation latency, and as-of identity/history gates."""

    if min(signal_at, confirmed_at, motion_at) <= 0:
        raise ValueError("capture times must be positive")
    if confirmed_at < signal_at or observation_latency_seconds < 0:
        raise ValueError("invalid confirmation or latency")
    alert_at = confirmed_at + observation_latency_seconds
    reasons = []
    if not prior_block:
        reasons.append("same_block_or_later")
    if alert_at >= motion_at:
        reasons.append("latency_exhausted_lead")
    if not as_of_qualified:
        reasons.append("wallet_or_kol_not_qualified_as_of_signal")
    actionable = not reasons
    return CaptureAssessment(
        kind=(CaptureKind.ONCHAIN_ADVANCE_CANDIDATE if actionable
              else CaptureKind.NOT_ACTIONABLE),
        actionable=actionable,
        alert_at=alert_at if actionable else None,
        seconds_to_motion=motion_at - alert_at,
        reasons=tuple(reasons) or ("qualified_onchain_advance_signal",),
    )


def assess_early_motion(
    first_small_move_at: int | None,
    motion_at: int | None,
    *,
    observation_latency_seconds: int,
) -> CaptureAssessment:
    """Classify 1.02x observation as detection, never advance prediction."""

    if observation_latency_seconds < 0:
        raise ValueError("latency cannot be negative")
    if first_small_move_at is None or motion_at is None:
        return CaptureAssessment(
            CaptureKind.NOT_ACTIONABLE, False, None, None,
            ("price_crossing_missing",),
        )
    if min(first_small_move_at, motion_at) <= 0:
        raise ValueError("capture times must be positive")
    alert_at = first_small_move_at + observation_latency_seconds
    actionable = alert_at < motion_at
    return CaptureAssessment(
        CaptureKind.EARLY_MOTION if actionable else CaptureKind.NOT_ACTIONABLE,
        actionable,
        alert_at if actionable else None,
        motion_at - alert_at,
        (("early_motion_window_available",) if actionable else
         ("latency_exhausted_early_motion_window",)),
    )


def combine_capture_lanes(
    public_event_assessments: Iterable[tuple[bool, bool]],
    provider_assessments: Iterable[CaptureAssessment],
    early_motion: CaptureAssessment,
) -> CaptureLaneCoverage:
    """Combine already assessed lanes without upgrading timing leads to skill."""

    public = tuple(public_event_assessments)
    providers = tuple(provider_assessments)
    public_advance = any(actionable for actionable, _ in public)
    fresh_public = any(actionable and fresh for actionable, fresh in public)
    provider_timing = any(
        item.seconds_to_motion is not None
        and item.seconds_to_motion > 0
        and set(item.reasons) == {"wallet_or_kol_not_qualified_as_of_signal"}
        for item in providers
    )
    qualified_provider = any(item.actionable for item in providers)
    return CaptureLaneCoverage(
        public_advance=public_advance,
        fresh_public_advance=fresh_public,
        provider_timing_ceiling=provider_timing,
        qualified_provider_advance=qualified_provider,
        timing_union_ceiling=public_advance or provider_timing,
        semantic_public_or_qualified_provider_advance=(
            public_advance or qualified_provider
        ),
        early_motion_detection=(
            early_motion.actionable
            and early_motion.kind == CaptureKind.EARLY_MOTION
        ),
    )
