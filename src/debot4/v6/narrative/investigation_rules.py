"""Deterministic rules shared by both narrative discovery entrances."""

from __future__ import annotations

from datetime import datetime

from .domain import ConsensusStage
from .investigation_domain import InvestigationPolicy, NarrativeEventKind
from .investigation_inputs import CapitalContext, NarrativeEvent


def validate_causal_graph(events: tuple[NarrativeEvent, ...]) -> None:
    by_id = {item.event_id: item for item in events}
    for event in events:
        for parent_id in event.parent_ids:
            parent = by_id.get(parent_id)
            if parent is None:
                raise ValueError(f"causal parent is missing: {parent_id}")
            if parent.published_at > event.published_at:
                raise ValueError("causal parents cannot occur after their children")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(event_id: str) -> None:
        if event_id in visiting:
            raise ValueError("narrative causal graph contains a cycle")
        if event_id in visited:
            return
        visiting.add(event_id)
        for parent_id in by_id[event_id].parent_ids:
            visit(parent_id)
        visiting.remove(event_id)
        visited.add(event_id)

    for event_id in by_id:
        visit(event_id)


def select_source(events: tuple[NarrativeEvent, ...]) -> NarrativeEvent | None:
    candidates = (
        item for item in events
        if item.kind is NarrativeEventKind.SOURCE_EVENT
        and item.actor.can_establish_origin
    )
    return min(candidates, key=_event_key, default=None)


def select_catalyst(
    events: tuple[NarrativeEvent, ...],
    source: NarrativeEvent | None,
) -> NarrativeEvent | None:
    if source is None:
        return None
    by_id = {item.event_id: item for item in events}
    candidates = [
        item for item in events
        if item.kind is NarrativeEventKind.CURRENT_CATALYST
        and item.actor.can_create_catalyst
        and descends_from(item, source.event_id, by_id)
    ]
    return max(candidates, key=_event_key, default=None)


def propagation_events(
    events: tuple[NarrativeEvent, ...],
    source: NarrativeEvent | None,
) -> tuple[NarrativeEvent, ...]:
    if source is None:
        return ()
    by_id = {item.event_id: item for item in events}
    eligible = (
        item for item in events
        if item.kind is NarrativeEventKind.PROPAGATION
        and item.actor.can_propagate
        and descends_from(item, source.event_id, by_id)
    )
    by_group: dict[str, NarrativeEvent] = {}
    for event in sorted(eligible, key=_event_key):
        by_group.setdefault(event.independence_group, event)
    return tuple(by_group.values())


def descends_from(
    event: NarrativeEvent,
    ancestor_id: str,
    events: dict[str, NarrativeEvent],
) -> bool:
    pending = list(event.parent_ids)
    visited: set[str] = set()
    while pending:
        parent_id = pending.pop()
        if parent_id == ancestor_id:
            return True
        if parent_id not in visited and parent_id in events:
            visited.add(parent_id)
            pending.extend(events[parent_id].parent_ids)
    return False


def capital_confirmations(
    capital: CapitalContext,
    cutoff: datetime,
    policy: InvestigationPolicy,
) -> tuple[bool, bool]:
    current = capital.current_debot
    current_ok = bool(
        current is not None
        and capital.current_debot_qualified
        and current.available_at <= cutoff
    )
    if current is None:
        return False, current_ok
    prior = any(
        item.signal_id != current.signal_id
        and item.event_at < current.event_at
        and item.available_at < current.available_at
        and item.available_at <= cutoff
        and (current.event_at - item.event_at).total_seconds()
        <= policy.maximum_historical_kol_age_seconds
        for item in capital.historical_kol
    )
    return prior, current_ok


def derive_stage(
    source: NarrativeEvent | None,
    catalyst: NarrativeEvent | None,
    propagation_count: int,
    cutoff: datetime,
    policy: InvestigationPolicy,
) -> ConsensusStage:
    if source is None:
        return ConsensusStage.UNRESOLVED
    fresh = catalyst is not None and (
        cutoff - catalyst.published_at
    ).total_seconds() <= policy.maximum_catalyst_age_seconds
    if fresh and propagation_count >= policy.expansion_propagation_groups:
        return ConsensusStage.EXPANSION
    if fresh and propagation_count >= policy.minimum_propagation_groups:
        source_age = (cutoff - source.published_at).total_seconds()
        return (
            ConsensusStage.REVIVAL
            if source_age > policy.maximum_catalyst_age_seconds
            else ConsensusStage.VALIDATION
        )
    if (cutoff - source.published_at).total_seconds() > policy.maximum_catalyst_age_seconds:
        return ConsensusStage.LATENT
    return ConsensusStage.DISCOVERY


def _event_key(event: NarrativeEvent) -> tuple[datetime, str]:
    return event.published_at, event.event_id
