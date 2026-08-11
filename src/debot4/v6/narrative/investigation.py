"""Unified active-monitor and passive-DeBot narrative investigation."""

from __future__ import annotations

from dataclasses import replace

from .actor_registry import ActorRegistry, DEFAULT_ACTOR_REGISTRY
from .hashing import canonical_sha256
from .investigation_domain import (
    InvestigationPolicy,
    NarrativeEventKind,
    NarrativeVerdict,
)
from .investigation_decision import (
    authoritative_counters,
    carrier_findings,
    decision_reasons,
    selected_binding,
)
from .investigation_inputs import InvestigationRequest
from .investigation_leaders import effective_binding, market_leader, narrative_leader
from .investigation_report import InvestigationReport
from .investigation_rules import (
    capital_confirmations,
    derive_stage,
    propagation_events,
    select_catalyst,
    select_source,
    validate_causal_graph,
)
from .investigation_sources import validate_event_sources


def investigate_narrative(
    request: InvestigationRequest,
    *,
    policy: InvestigationPolicy = InvestigationPolicy(),
    actor_registry: ActorRegistry = DEFAULT_ACTOR_REGISTRY,
) -> InvestigationReport:
    """Produce the same evidence contract from either discovery entrance."""

    validate_event_sources(request.events, actor_registry, request.narrative_key)
    validate_causal_graph(request.events)
    events = tuple(
        sorted(
            (item for item in request.events if item.usable_at(request.as_of)),
            key=lambda item: (item.published_at, item.first_seen_at, item.event_id),
        )
    )
    by_id = {item.event_id: item for item in events}
    source = select_source(events)
    catalyst = select_catalyst(events, source)
    propagation = propagation_events(events, source)
    bindings = {
        item.token.address: effective_binding(item, by_id, source)
        for item in request.carriers
    }
    leader = narrative_leader(request.carriers, bindings)
    market = market_leader(request.carriers, request.as_of)
    historical, current = capital_confirmations(
        request.capital, request.as_of, policy
    )
    stage = derive_stage(
        source, catalyst, len(propagation), request.as_of, policy
    )
    counters = tuple(
        item for item in events if item.kind is NarrativeEventKind.COUNTER_EVIDENCE
    )
    hard_counters = authoritative_counters(counters, leader, request)
    rejects, waits, unknowns = decision_reasons(
        request, policy, source, catalyst, len(propagation), bindings,
        leader, market, historical, current, stage, counters, hard_counters,
    )
    verdict = (
        NarrativeVerdict.REJECT if rejects
        else NarrativeVerdict.WAIT if waits
        else NarrativeVerdict.BUY_CANDIDATE
    )
    reasons = tuple(dict.fromkeys(rejects or waits or ["narrative_buy_candidate"]))
    carrier_binding = selected_binding(request, bindings, leader)
    report = InvestigationReport(
        identity="pending",
        identity_hash="pending",
        mode=request.mode,
        trigger_id=request.trigger_id,
        narrative_key=request.narrative_key,
        as_of=request.as_of,
        source_event_id=None if source is None else source.event_id,
        source_actor_handle=None if source is None else source.actor.handle,
        source_actor_tier=None if source is None else source.actor.tier,
        propagation_reason=(
            None if not propagation
            else "; ".join(item.claim for item in propagation)
        ),
        current_catalyst_id=None if catalyst is None else catalyst.event_id,
        carrier_binding=carrier_binding,
        narrative_leader=leader,
        market_leader=market,
        carriers=carrier_findings(request, bindings, leader, market),
        historical_kol_confirmed=historical,
        current_debot_confirmed=current,
        stage=stage,
        pump_phase=request.pump_phase,
        verdict=verdict,
        reasons=reasons,
        unknowns=tuple(dict.fromkeys(unknowns)),
        counterevidence_ids=tuple(item.event_id for item in counters),
        invalidation_conditions=tuple(dict.fromkeys(
            item.strip() for item in request.invalidation_conditions if item.strip()
        )),
        timeline=tuple(item.event_id for item in events),
    )
    digest = canonical_sha256(report.to_payload(include_identity=False))
    return replace(
        report,
        identity=f"v6.narrative_investigation.v1:{digest}",
        identity_hash=digest,
    )
