"""Categorical v6 narrative readiness with no aggregate score."""

from __future__ import annotations

from dataclasses import dataclass

from .domain import (
    Canonicality,
    ConsensusStage,
    Dimension,
    FindingState,
    Readiness,
    ValuationStatus,
)
from .dossier import NarrativeDossier
from .valuation import ValuationView


_HARD = (Dimension.ORIGIN, Dimension.LEGITIMACY, Dimension.LEADER_COMPETITION)
_SOFT = (
    Dimension.PROPAGATION,
    Dimension.CULTURAL_FIT,
    Dimension.CATALYSTS,
    Dimension.CONSENSUS_STAGE,
)
_RESOLVED = {
    Canonicality.OFFICIAL_EXACT_CA,
    Canonicality.CREATOR_CLAIMED,
    Canonicality.COMMUNITY_CONSENSUS,
}


@dataclass(frozen=True, slots=True)
class ReadinessPolicy:
    require_capital_confirmation: bool = True
    require_bounded_valuation: bool = True


@dataclass(frozen=True, slots=True)
class ReadinessDecision:
    status: Readiness
    reasons: tuple[str, ...]


def evaluate_readiness(
    dossier: NarrativeDossier,
    *,
    valuation: ValuationView | None = None,
    policy: ReadinessPolicy = ReadinessPolicy(),
) -> ReadinessDecision:
    states = {dimension: dossier.effective_state(dimension) for dimension in Dimension}
    rejects = [
        f"{dimension.value}_contradicted"
        for dimension, state in states.items()
        if state is FindingState.CONTRADICTED
    ]
    if dossier.canonicality is Canonicality.CONTRADICTED:
        rejects.append("token_binding_contradicted")
    if dossier.stage is ConsensusStage.DECAY:
        rejects.append("narrative_in_decay")
    if valuation is not None and valuation.status is ValuationStatus.OVEREXTENDED:
        rejects.append("valuation_overextended")
    if rejects:
        return _decision(Readiness.REJECT, rejects)
    unresolved = [
        f"{dimension.value}_unresolved"
        for dimension in _HARD
        if states[dimension] in {FindingState.UNKNOWN, FindingState.SPECULATIVE}
    ]
    if dossier.canonicality in {Canonicality.OPEN_RACE, Canonicality.UNKNOWN}:
        unresolved.append("canonical_token_unresolved")
    if unresolved:
        return _decision(Readiness.UNRESOLVED, unresolved)
    waits: list[str] = []
    waits.extend(
        f"{dimension.value}_not_confirmed"
        for dimension in _HARD
        if states[dimension] is not FindingState.CONFIRMED
    )
    waits.extend(
        f"{dimension.value}_not_supported"
        for dimension in _SOFT
        if states[dimension] not in {FindingState.CONFIRMED, FindingState.SUPPORTED}
    )
    if dossier.canonicality not in _RESOLVED:
        waits.append("canonical_token_only_provisional")
    if dossier.stage not in {ConsensusStage.VALIDATION, ConsensusStage.EXPANSION}:
        waits.append(f"consensus_stage:{dossier.stage.value}")
    if policy.require_capital_confirmation and not dossier.has_capital_confirmation:
        waits.append("missing_capital_confirmation")
    if policy.require_bounded_valuation and (
        valuation is None or valuation.status is not ValuationStatus.BOUNDED
    ):
        waits.append("valuation_not_bounded")
    if valuation is not None and valuation.as_of > dossier.as_of:
        waits.append("valuation_not_available_at_decision")
    waits.extend(f"fatal_unknown:{item}" for item in dossier.fatal_unknowns)
    return _decision(Readiness.WAIT if waits else Readiness.PASS_TO_EXECUTION, waits)


def _decision(status: Readiness, reasons: list[str]) -> ReadinessDecision:
    return ReadinessDecision(status, tuple(dict.fromkeys(reasons)))
