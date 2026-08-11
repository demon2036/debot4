"""Pure assembly of a point-in-time partial narrative dossier."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from .domain import (
    Canonicality,
    ConsensusStage,
    Dimension,
    DimensionFinding,
    FindingState,
    TokenRef,
)
from .dossier import NarrativeDossier
from .evidence import EvidenceItem
from .binding import assess_primary_binding
from .hashing import canonical_sha256, dossier_hash
from .history import assess_historical_kol_buys
from .models import (
    CurrentSignalBoundary,
    HistoricalKolFact,
    RESEARCH_SCHEMA,
    ResearchOutcome,
    StatusResearch,
    aware_utc,
    is_exact_bsc_token,
)
from .results import (
    BindingAssessment,
    LiveDossierBuild,
    NarrativeResearchResult,
    ResearchStatus,
)


def build_live_dossier(
    token: TokenRef,
    source_research: StatusResearch,
    historical_kol_evidence: Iterable[HistoricalKolFact],
    *,
    decision_time: datetime,
    current_signal: CurrentSignalBoundary | None,
) -> LiveDossierBuild:
    cutoff = aware_utc(decision_time, "decision_time")
    binding = assess_primary_binding(token, source_research, decision_time=cutoff)
    history = assess_historical_kol_buys(
        token,
        historical_kol_evidence,
        current_signal=current_signal,
        decision_time=cutoff,
    )
    dossier = _dossier(token, cutoff, binding, history.evidence)
    rejects = _reject_reasons(
        token, source_research, binding.reason, current_signal, cutoff
    )
    waits: list[str] = []
    community_candidate = (
        source_research.outcome is ResearchOutcome.FETCHED
        and binding.reason == "target_ca_not_mentioned"
    )
    if not binding.accepted and not community_candidate:
        waits.append(binding.reason)
    if not history.qualified:
        waits.append(history.reason)
    status = ResearchStatus.REJECT if rejects else (
        ResearchStatus.WAIT if waits else ResearchStatus.READY
    )
    ready_reason = (
        "research_prerequisites_ready"
        if binding.accepted
        else "community_narrative_prerequisites_ready"
    )
    reasons = tuple(dict.fromkeys(rejects or waits or [ready_reason]))
    dossier_digest = dossier_hash(dossier)
    material = {
        "schema": RESEARCH_SCHEMA,
        "decision_time": cutoff.isoformat(),
        "source_research": source_research.to_payload(),
        "binding": binding.to_payload(),
        "historical_kol": history.to_payload(),
        "current_signal": None if current_signal is None else current_signal.to_payload(),
        "dossier_hash": dossier_digest,
    }
    digest = canonical_sha256(material)
    result = NarrativeResearchResult(
        status=status,
        reasons=reasons,
        decision_time=cutoff,
        source_research=source_research,
        binding=binding,
        historical_kol=history,
        current_signal=current_signal,
        identity=f"{RESEARCH_SCHEMA}:{digest}",
        identity_hash=digest,
        dossier_hash=dossier_digest,
    )
    return LiveDossierBuild(dossier=dossier, research=result)


def _dossier(
    token: TokenRef,
    cutoff: datetime,
    binding: BindingAssessment,
    history: tuple[EvidenceItem, ...],
) -> NarrativeDossier:
    item = binding.evidence
    evidence = (() if item is None else (item,)) + history
    if binding.accepted:
        findings = (
            DimensionFinding(
                Dimension.ORIGIN,
                FindingState.CONFIRMED,
                "A primary-linked X status self-published the exact contract",
                supports=(item.evidence_id,),
            ),
            DimensionFinding(
                Dimension.LEGITIMACY,
                FindingState.CONFIRMED,
                "The primary-linked status positively binds this exact CA",
                supports=(item.evidence_id,),
            ),
        )
        canonicality = Canonicality.CREATOR_CLAIMED
        thesis = "A primary-linked X status positively binds the exact BSC contract"
        unknowns = _UNRESOLVED_DIMENSIONS
    else:
        findings = (
            DimensionFinding(
                Dimension.ORIGIN, FindingState.UNKNOWN,
                "No usable primary origin binding exists at the cutoff",
                unknowns=("primary_actor_exact_ca_binding",),
            ),
            DimensionFinding(
                Dimension.LEGITIMACY, FindingState.UNKNOWN,
                "Exact contract legitimacy remains unresolved",
                unknowns=("positive_primary_exact_ca_binding",),
            ),
        )
        canonicality = Canonicality.UNKNOWN
        thesis = "Narrative identity remains unresolved at the decision cutoff"
        unknowns = ("primary_exact_ca_binding", *_UNRESOLVED_DIMENSIONS)
    return NarrativeDossier(
        token=token,
        as_of=cutoff,
        thesis=thesis,
        canonicality=canonicality,
        stage=ConsensusStage.UNRESOLVED,
        evidence=evidence,
        findings=findings,
        fatal_unknowns=unknowns,
    )


def _reject_reasons(
    token: TokenRef,
    research: StatusResearch,
    binding_reason: str,
    current: CurrentSignalBoundary | None,
    cutoff: datetime,
) -> list[str]:
    reasons: list[str] = []
    if not is_exact_bsc_token(token):
        reasons.append("unsupported_token_identity")
    if current is not None and current.available_at > cutoff:
        reasons.append("current_signal_from_future")
    if research.outcome is ResearchOutcome.REJECT:
        reasons.append(research.reason)
    if binding_reason in {
        "research_token_mismatch",
        "research_identity_mismatch",
        "research_time_invalid",
        "target_ca_mismatch",
        "conflicting_ca_mentions",
        "target_ca_negated",
    }:
        reasons.append(binding_reason)
    return list(dict.fromkeys(reasons))


_UNRESOLVED_DIMENSIONS = (
    "propagation",
    "cultural_fit",
    "catalysts",
    "leader_competition",
    "consensus_stage",
    "valuation_anchor",
    "invalidation",
)
