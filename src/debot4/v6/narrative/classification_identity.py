"""Creator and community token-identity conclusions."""

from __future__ import annotations

from dataclasses import dataclass

from .classification_evidence import debot_item, primary_item
from .classification_rules import NarrativeSignals
from .classification_spread import SpreadAssessment
from .domain import (
    Canonicality,
    Dimension,
    DimensionFinding,
    EvidenceRole,
    FindingState,
)
from .evidence import EvidenceItem
from .live_context import DeBotNarrativeContext
from .results import LiveDossierBuild


@dataclass(frozen=True, slots=True)
class IdentityAssessment:
    canonicality: Canonicality
    leader_state: FindingState
    leader_evidence: tuple[EvidenceItem, ...]
    findings: tuple[DimensionFinding, ...] = ()
    evidence: tuple[EvidenceItem, ...] = ()
    unknowns: tuple[str, ...] = ()


def assess_identity(
    base: LiveDossierBuild,
    context: DeBotNarrativeContext,
    signals: NarrativeSignals,
    spread: SpreadAssessment,
) -> IdentityAssessment:
    if base.research.binding.accepted:
        leader = primary_item(
            base,
            EvidenceRole.LEADER_COMPETITION,
            "The creator's exact-CA declaration identifies this token as the leader",
        )
        state = FindingState.CONFIRMED if signals.creator_leader else FindingState.UNKNOWN
        return IdentityAssessment(
            Canonicality.CREATOR_CLAIMED,
            state,
            () if leader is None else (leader,),
            unknowns=() if state is FindingState.CONFIRMED else ("canonical_leader_unverified",),
        )
    if not signals.community_candidate:
        return IdentityAssessment(
            Canonicality.PROVISIONAL_LEADER,
            FindingState.UNKNOWN,
            (),
            unknowns=("canonical_leader_unverified",),
        )
    return _community_identity(base, context, spread)


def _community_identity(
    base: LiveDossierBuild,
    context: DeBotNarrativeContext,
    spread: SpreadAssessment,
) -> IdentityAssessment:
    origin = primary_item(
        base,
        EvidenceRole.ORIGIN,
        "The exact X status is the observed origin of the matching meme narrative",
    )
    if origin is None:
        return IdentityAssessment(
            Canonicality.PROVISIONAL_LEADER,
            FindingState.UNKNOWN,
            (),
            unknowns=("narrative_origin_unverified", "canonical_leader_unverified"),
        )
    binding = debot_item(
        context,
        base.dossier.as_of,
        EvidenceRole.NARRATIVE_BINDING,
        "DeBot associates the exact token with the narrative; this is not creator CA endorsement",
    )
    items = (origin, binding)
    confirmed = spread.validation_reached
    legitimacy_state = FindingState.CONFIRMED if confirmed else FindingState.SUPPORTED
    canonicality = (
        Canonicality.COMMUNITY_CONSENSUS
        if confirmed
        else Canonicality.PROVISIONAL_LEADER
    )
    findings = (
        DimensionFinding(
            Dimension.ORIGIN,
            FindingState.CONFIRMED,
            origin.claim,
            supports=(origin.evidence_id,),
        ),
        DimensionFinding(
            Dimension.LEGITIMACY,
            legitimacy_state,
            "; ".join(item.claim for item in items),
            supports=tuple(item.evidence_id for item in items),
        ),
    )
    leader_items = (*items, *spread.evidence) if confirmed else items
    return IdentityAssessment(
        canonicality,
        FindingState.CONFIRMED if confirmed else FindingState.SUPPORTED,
        leader_items,
        findings,
        items,
    )
