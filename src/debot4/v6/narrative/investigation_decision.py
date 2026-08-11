"""Fail-closed verdict and carrier-role rules for narrative investigations."""

from __future__ import annotations

from .domain import ConsensusStage, TokenRef
from .investigation_domain import CarrierBinding, InvestigationPolicy, PumpPhase
from .investigation_inputs import InvestigationRequest, NarrativeEvent
from .investigation_report import CarrierFinding


_ACTIVE_STAGES = {
    ConsensusStage.VALIDATION,
    ConsensusStage.EXPANSION,
    ConsensusStage.REVIVAL,
}


def decision_reasons(
    request: InvestigationRequest,
    policy: InvestigationPolicy,
    source: NarrativeEvent | None,
    catalyst: NarrativeEvent | None,
    propagation_count: int,
    bindings: dict[str, CarrierBinding],
    leader: TokenRef | None,
    market: TokenRef | None,
    historical: bool,
    current: bool,
    stage: ConsensusStage,
    counters: tuple[NarrativeEvent, ...],
    hard_counters: tuple[NarrativeEvent, ...],
) -> tuple[list[str], list[str], list[str]]:
    rejects: list[str] = []
    waits: list[str] = []
    unknowns: list[str] = []
    trigger = None if request.trigger_token is None else request.trigger_token.address
    if hard_counters:
        rejects.append("authoritative_counterevidence")
    if trigger is not None and bindings.get(trigger) is CarrierBinding.CONTRADICTED:
        rejects.append("debot_trigger_carrier_contradicted")
    if trigger is not None and leader is not None and request.trigger_token != leader:
        rejects.append("debot_trigger_is_not_narrative_leader")
    if request.pump_phase is PumpPhase.POST_PUMP:
        rejects.append("post_pump_entry_rejected")
    _missing(source, "source_event_unresolved", waits, unknowns)
    _missing(catalyst, "current_catalyst_unresolved", waits, unknowns)
    if catalyst is not None and (
        request.as_of - catalyst.published_at
    ).total_seconds() > policy.maximum_catalyst_age_seconds:
        waits.append("current_catalyst_stale")
    if propagation_count < policy.minimum_propagation_groups:
        waits.append("independent_narrative_propagation_unresolved")
        unknowns.append("minimum_two_independent_propagation_groups")
    _missing(leader, "narrative_leader_unresolved", waits, unknowns)
    if market is not None and leader is not None and market != leader:
        waits.append("market_leader_differs_from_narrative_leader")
    if not historical:
        waits.append("recent_historical_kol_confirmation_missing")
    if not current:
        waits.append("current_debot_confirmation_missing")
    if stage not in _ACTIVE_STAGES:
        waits.append(f"narrative_stage:{stage.value}")
    if request.pump_phase is PumpPhase.UNKNOWN:
        waits.append("pump_phase_unresolved")
    elif request.pump_phase is PumpPhase.DURING_PUMP:
        waits.append("price_acceleration_requires_entry_recheck")
    if not request.invalidation_conditions:
        waits.append("invalidation_conditions_missing")
    if counters and not hard_counters:
        waits.append("counterevidence_requires_resolution")
    return rejects, waits, unknowns


def authoritative_counters(
    events: tuple[NarrativeEvent, ...],
    leader: TokenRef | None,
    request: InvestigationRequest,
) -> tuple[NarrativeEvent, ...]:
    targets = {
        item for item in (
            None if leader is None else leader.address,
            None if request.trigger_token is None else request.trigger_token.address,
        ) if item is not None
    }
    return tuple(
        item for item in events
        if item.actor.can_counter_authoritatively
        and (not item.token_address or item.token_address in targets)
    )


def selected_binding(
    request: InvestigationRequest,
    bindings: dict[str, CarrierBinding],
    leader: TokenRef | None,
) -> CarrierBinding:
    target = request.trigger_token or leader
    return CarrierBinding.UNVERIFIED if target is None else bindings.get(
        target.address, CarrierBinding.UNVERIFIED
    )


def carrier_findings(
    request: InvestigationRequest,
    bindings: dict[str, CarrierBinding],
    leader: TokenRef | None,
    market: TokenRef | None,
) -> tuple[CarrierFinding, ...]:
    findings = []
    for item in request.carriers:
        narrative = item.token == leader
        market_role = item.token == market
        role = (
            "narrative_and_market_leader" if narrative and market_role
            else "narrative_leader" if narrative
            else "market_leader_imitation" if market_role and leader is not None
            else "imitation" if leader is not None
            else "contender"
        )
        findings.append(CarrierFinding(
            item.token, item.symbol, bindings[item.token.address], role,
            item.binding_event_ids,
        ))
    return tuple(findings)


def _missing(
    value: object | None,
    reason: str,
    waits: list[str],
    unknowns: list[str],
) -> None:
    if value is None:
        waits.append(reason)
        unknowns.append(reason)
