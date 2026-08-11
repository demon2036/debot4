"""Categorical narrative classification with strict evidence roles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .classification_evidence import current_capital_item, debot_item, primary_item
from .classification_identity import assess_identity
from .classification_rules import (
    NarrativeSignals,
    analyze_context,
    classification_thesis,
    classify_stage,
)
from .classification_spread import assess_spread
from .domain import (
    Canonicality,
    ConsensusStage,
    Dimension,
    DimensionFinding,
    EvidenceRole,
    FindingState,
)
from .evidence import EvidenceItem
from .live_context import DeBotNarrativeContext
from .results import LiveDossierBuild


@dataclass(frozen=True, slots=True)
class ContextClassification:
    canonicality: Canonicality
    stage: ConsensusStage
    thesis: str
    evidence: tuple[EvidenceItem, ...]
    findings: tuple[DimensionFinding, ...]
    fatal_unknowns: tuple[str, ...]


def classify_context(
    base: LiveDossierBuild,
    context: DeBotNarrativeContext,
    *,
    propagation_evidence: Iterable[EvidenceItem] = (),
) -> ContextClassification:
    signals = analyze_context(base, context)
    if signals.conflict:
        return _contradicted(base, context, signals)
    spread = assess_spread(base, propagation_evidence)
    identity = assess_identity(base, context, signals, spread)
    evidence = list(identity.evidence)
    findings = list(identity.findings)
    unknowns = list(identity.unknowns)

    culture = primary_item(
        base,
        EvidenceRole.CULTURAL_CONTEXT,
        "The exact X status carries the meme's independently reviewable cultural theme",
    )
    _add(
        Dimension.CULTURAL_FIT,
        signals.culture,
        "cultural_fit_unverified",
        (culture,),
        evidence,
        findings,
        unknowns,
    )
    catalyst = primary_item(
        base,
        EvidenceRole.CATALYST,
        "The exact X status contains an explicit launch or event catalyst",
    )
    _add(
        Dimension.CATALYSTS,
        signals.catalyst,
        "catalyst_unverified",
        (catalyst,),
        evidence,
        findings,
        unknowns,
    )
    _add_state(
        Dimension.LEADER_COMPETITION,
        identity.leader_state,
        "canonical_leader_unverified",
        identity.leader_evidence,
        evidence,
        findings,
        unknowns,
    )
    _add(
        Dimension.PROPAGATION,
        spread.propagated,
        "independent_narrative_propagation_unverified",
        spread.evidence,
        evidence,
        findings,
        unknowns,
    )
    _add(
        Dimension.CONSENSUS_STAGE,
        spread.validation_reached,
        "narrative_consensus_stage_unverified",
        spread.evidence,
        evidence,
        findings,
        unknowns,
    )
    if signals.current_kol:
        _include(evidence, (current_capital_item(context, base.dossier.as_of),))
    else:
        unknowns.append("current_capital_confirmation_unverified")
    if not signals.historical_kol:
        unknowns.append("historical_capital_confirmation_unverified")
    return ContextClassification(
        identity.canonicality,
        classify_stage(base, validation_reached=spread.validation_reached),
        classification_thesis(context, signals.shared_terms),
        tuple(evidence),
        tuple(findings),
        tuple(dict.fromkeys(unknowns)),
    )


def _contradicted(
    base: LiveDossierBuild,
    context: DeBotNarrativeContext,
    signals: NarrativeSignals,
) -> ContextClassification:
    counter = debot_item(
        context,
        base.dossier.as_of,
        EvidenceRole.COUNTER_EVIDENCE,
        "The exact status or DeBot context contains a conflicting contract claim",
    )
    finding = DimensionFinding(
        Dimension.LEADER_COMPETITION,
        FindingState.CONTRADICTED,
        "Observed sources contradict the canonical-token association",
        contradicts=(counter.evidence_id,),
    )
    return ContextClassification(
        Canonicality.CONTRADICTED,
        classify_stage(base, validation_reached=False),
        classification_thesis(context, (), contradicted=True),
        (counter,),
        (finding,),
        (),
    )


def _add(
    dimension: Dimension,
    accepted: bool,
    unknown: str,
    items: tuple[EvidenceItem | None, ...],
    evidence: list[EvidenceItem],
    findings: list[DimensionFinding],
    unknowns: list[str],
) -> None:
    state = FindingState.SUPPORTED if accepted else FindingState.UNKNOWN
    _add_state(dimension, state, unknown, items, evidence, findings, unknowns)


def _add_state(
    dimension: Dimension,
    state: FindingState,
    unknown: str,
    items: tuple[EvidenceItem | None, ...],
    evidence: list[EvidenceItem],
    findings: list[DimensionFinding],
    unknowns: list[str],
) -> None:
    usable = tuple(item for item in items if item is not None)
    if state in {FindingState.CONFIRMED, FindingState.SUPPORTED} and usable:
        _include(evidence, usable)
        findings.append(DimensionFinding(
            dimension,
            state,
            "; ".join(item.claim for item in usable),
            supports=tuple(item.evidence_id for item in usable),
        ))
        return
    findings.append(DimensionFinding(
        dimension,
        FindingState.UNKNOWN,
        f"{dimension.value} is not yet evidenced",
        unknowns=(unknown,),
    ))
    unknowns.append(unknown)


def _include(target: list[EvidenceItem], items: tuple[EvidenceItem, ...]) -> None:
    known = {item.evidence_id for item in target}
    target.extend(item for item in items if item.evidence_id not in known)
