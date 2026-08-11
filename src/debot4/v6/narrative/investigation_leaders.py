"""Evidence-bound narrative and market leader selection."""

from __future__ import annotations

from datetime import datetime

from .actors import ActorTier
from .domain import TokenRef
from .investigation_domain import CarrierBinding, NarrativeEventKind
from .investigation_inputs import CarrierCandidate, NarrativeEvent
from .investigation_rules import descends_from


_PRIORITY = {
    CarrierBinding.OFFICIAL_EXACT_CA: 3,
    CarrierBinding.CREATOR_EXACT_CA: 3,
    CarrierBinding.COMMUNITY_CONSENSUS: 2,
    CarrierBinding.UNVERIFIED: 1,
    CarrierBinding.CONTRADICTED: 0,
}


def effective_binding(
    candidate: CarrierCandidate,
    events: dict[str, NarrativeEvent],
    source: NarrativeEvent | None,
) -> CarrierBinding:
    if source is None:
        return CarrierBinding.UNVERIFIED
    selected = tuple(
        events[event_id] for event_id in candidate.binding_event_ids
        if event_id in events
    )
    matching = tuple(
        item for item in selected
        if item.token_address == candidate.token.address
        and item.exact_ca
        and item.kind in {
            NarrativeEventKind.TOKEN_BINDING,
            NarrativeEventKind.COUNTER_EVIDENCE,
        }
        and item.published_at >= candidate.created_at
        and (
            item.kind is NarrativeEventKind.COUNTER_EVIDENCE
            or descends_from(item, source.event_id, events)
        )
    )
    if candidate.binding is CarrierBinding.CONTRADICTED:
        return (
            CarrierBinding.CONTRADICTED
            if any(item.kind is NarrativeEventKind.COUNTER_EVIDENCE for item in matching)
            else CarrierBinding.UNVERIFIED
        )
    bindings = tuple(
        item for item in matching if item.kind is NarrativeEventKind.TOKEN_BINDING
    )
    if candidate.binding is CarrierBinding.OFFICIAL_EXACT_CA:
        valid = any(item.actor.tier in {
            ActorTier.GLOBAL_AGENDA,
            ActorTier.ECOSYSTEM_AUTHORITY,
        } and item.actor.can_bind_token for item in bindings)
        return candidate.binding if valid else CarrierBinding.UNVERIFIED
    if candidate.binding is CarrierBinding.CREATOR_EXACT_CA:
        valid = any(
            item.actor.tier is ActorTier.ORIGINAL_CREATOR
            and item.actor.can_bind_token
            for item in bindings
        )
        return candidate.binding if valid else CarrierBinding.UNVERIFIED
    if candidate.binding is CarrierBinding.COMMUNITY_CONSENSUS:
        groups = {item.independence_group for item in bindings}
        return candidate.binding if len(groups) >= 2 else CarrierBinding.UNVERIFIED
    return CarrierBinding.UNVERIFIED


def narrative_leader(
    candidates: tuple[CarrierCandidate, ...],
    bindings: dict[str, CarrierBinding],
) -> TokenRef | None:
    if not candidates:
        return None
    best = max(_PRIORITY[bindings[item.token.address]] for item in candidates)
    if best <= _PRIORITY[CarrierBinding.UNVERIFIED]:
        return None
    leaders = [
        item.token for item in candidates
        if _PRIORITY[bindings[item.token.address]] == best
    ]
    return leaders[0] if len(leaders) == 1 else None


def market_leader(
    candidates: tuple[CarrierCandidate, ...], cutoff: datetime
) -> TokenRef | None:
    known = [
        item for item in candidates
        if item.market_cap_usd is not None and item.market_as_of <= cutoff
    ]
    if not known:
        return None
    highest = max(item.market_cap_usd for item in known)
    leaders = [item.token for item in known if item.market_cap_usd == highest]
    return leaders[0] if len(leaders) == 1 else None
