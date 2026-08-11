"""Assemble an executable dossier from independently classified evidence."""

from typing import Iterable

from .classification import classify_context
from .domain import DimensionFinding
from .dossier import NarrativeDossier
from .evidence import EvidenceItem
from .live_context import DeBotNarrativeContext
from .results import LiveDossierBuild, bind_research_to_dossier


def build_executable_dossier(
    base: LiveDossierBuild,
    context: DeBotNarrativeContext,
    *,
    propagation_evidence: Iterable[EvidenceItem] = (),
) -> LiveDossierBuild:
    """Complete a dossier only when every required narrative claim is evidenced."""

    token = base.dossier.token
    if context.token_address != token.address:
        raise ValueError("DeBot context token does not match dossier token")
    classified = classify_context(
        base,
        context,
        propagation_evidence=propagation_evidence,
    )
    dossier = NarrativeDossier(
        token=token,
        as_of=base.dossier.as_of,
        thesis=classified.thesis,
        canonicality=classified.canonicality,
        stage=classified.stage,
        evidence=_merge_evidence(base.dossier.evidence, classified.evidence),
        findings=_merge_findings(base.dossier.findings, classified.findings),
        fatal_unknowns=classified.fatal_unknowns,
    )
    return LiveDossierBuild(dossier, bind_research_to_dossier(base.research, dossier))


def _merge_evidence(
    base: tuple[EvidenceItem, ...],
    classified: tuple[EvidenceItem, ...],
) -> tuple[EvidenceItem, ...]:
    merged: dict[str, EvidenceItem] = {}
    for item in (*base, *classified):
        previous = merged.get(item.evidence_id)
        if previous is not None and previous != item:
            raise ValueError("conflicting evidence id")
        merged[item.evidence_id] = item
    return tuple(merged.values())


def _merge_findings(
    base: tuple[DimensionFinding, ...],
    classified: tuple[DimensionFinding, ...],
) -> tuple[DimensionFinding, ...]:
    merged = {item.dimension: item for item in base}
    merged.update({item.dimension: item for item in classified})
    return tuple(merged.values())
