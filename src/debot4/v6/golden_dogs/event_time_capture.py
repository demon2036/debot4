"""Pure event-time ceiling for public signals before transaction motion."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AdvanceLane(str, Enum):
    INDEPENDENT = "independent_public"
    PROJECT = "project_public"
    AUTOMATION = "automation_public"
    RELAY = "relay_public"


class AdvanceFreshness(str, Enum):
    FRESH = "fresh_pre_motion"
    STANDING = "standing_pre_wave"


@dataclass(frozen=True, slots=True)
class PublicAdvanceEvent:
    source: str
    event_id: str
    occurred_at: int
    lane: AdvanceLane
    exact_ca_bound: bool
    semantically_forward: bool


@dataclass(frozen=True, slots=True)
class EventTimeAssessment:
    source: str
    event_id: str
    lane: AdvanceLane
    freshness: AdvanceFreshness | None
    event_time_actionable: bool
    alert_at: int | None
    seconds_to_first_1_02: int | None
    reasons: tuple[str, ...]


LEAD_TIME_BUCKETS = (
    "lt_60s",
    "60s_to_lt_300s",
    "300s_to_lt_1800s",
    "1800s_to_lt_21600s",
    "21600s_to_lt_86400s",
    "gte_86400s",
)


def lead_time_bucket(seconds: int) -> str:
    """Place a strictly pre-motion lead in an explicit half-open age bucket."""

    if not isinstance(seconds, int) or isinstance(seconds, bool) or seconds <= 0:
        raise ValueError("lead seconds must be a positive integer")
    limits = (60, 300, 1_800, 21_600, 86_400)
    for limit, bucket in zip(limits, LEAD_TIME_BUCKETS):
        if seconds < limit:
            return bucket
    return LEAD_TIME_BUCKETS[-1]


def assess_public_event_time(
    event: PublicAdvanceEvent,
    *,
    fresh_start: int,
    first_1_02_at: int,
    assumed_latency_seconds: int,
) -> EventTimeAssessment:
    """Assess a counterfactual subscriber; this is not observed live capture."""

    if min(event.occurred_at, fresh_start, first_1_02_at) <= 0:
        raise ValueError("event and wave times must be positive")
    if assumed_latency_seconds < 0:
        raise ValueError("latency cannot be negative")
    alert_at = event.occurred_at + assumed_latency_seconds
    reasons = []
    if not event.semantically_forward:
        reasons.append("not_forward_semantic")
    if not event.exact_ca_bound:
        reasons.append("exact_ca_unresolved")
    if alert_at >= first_1_02_at:
        reasons.append("not_before_first_1_02")
    actionable = not reasons
    freshness = None
    if actionable:
        freshness = (
            AdvanceFreshness.FRESH if event.occurred_at >= fresh_start
            else AdvanceFreshness.STANDING
        )
    return EventTimeAssessment(
        source=event.source,
        event_id=event.event_id,
        lane=event.lane,
        freshness=freshness,
        event_time_actionable=actionable,
        alert_at=alert_at if actionable else None,
        seconds_to_first_1_02=first_1_02_at - alert_at,
        reasons=tuple(reasons) or ("event_time_pre_1_02_ceiling",),
    )
