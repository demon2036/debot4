"""Immutable v6 narrative dossier assembled at an explicit cutoff."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .domain import (
    Canonicality,
    ConsensusStage,
    Dimension,
    DimensionFinding,
    EvidenceRole,
    EvidenceSource,
    FindingState,
    TokenRef,
)
from .evidence import EvidenceItem, usable_ids
from .models import aware_utc


@dataclass(frozen=True, slots=True)
class NarrativeDossier:
    token: TokenRef
    as_of: datetime
    thesis: str
    canonicality: Canonicality
    stage: ConsensusStage
    evidence: tuple[EvidenceItem, ...]
    findings: tuple[DimensionFinding, ...]
    alternative_theses: tuple[str, ...] = ()
    fatal_unknowns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", aware_utc(self.as_of, "as_of"))
        object.__setattr__(self, "canonicality", Canonicality(self.canonicality))
        object.__setattr__(self, "stage", ConsensusStage(self.stage))
        if not self.thesis.strip():
            raise ValueError("thesis must not be empty")
        evidence_by_id = {item.evidence_id: item for item in self.evidence}
        if len(evidence_by_id) != len(self.evidence):
            raise ValueError("evidence ids must be unique")
        findings = {item.dimension: item for item in self.findings}
        if len(findings) != len(self.findings):
            raise ValueError("each dimension may appear only once")
        for item in self.evidence:
            if item.token_address and item.token_address != self.token.address:
                raise ValueError("evidence token does not match dossier token")
        for finding in self.findings:
            refs = (*finding.supports, *finding.contradicts)
            if set(refs) - evidence_by_id.keys():
                raise ValueError("finding references unknown evidence")
            if any(evidence_by_id[ref].role is EvidenceRole.CAPITAL_CONFIRMATION for ref in refs):
                raise ValueError("capital confirmation cannot prove narrative dimensions")
            if finding.dimension is Dimension.LEGITIMACY and finding.state in {
                FindingState.CONFIRMED,
                FindingState.SUPPORTED,
            }:
                binding = tuple(evidence_by_id[ref] for ref in finding.supports)
                allowed = {EvidenceSource.PRIMARY_ACTOR, EvidenceSource.OFFICIAL_SITE}
                creator_bound = binding and all(
                    item.role is EvidenceRole.TOKEN_BINDING
                    and item.exact_ca
                    and item.source in allowed
                    for item in binding
                )
                community_bound = (
                    self.canonicality in {
                        Canonicality.COMMUNITY_CONSENSUS,
                        Canonicality.PROVISIONAL_LEADER,
                    }
                    and (
                        self.canonicality is Canonicality.COMMUNITY_CONSENSUS
                        or finding.state is FindingState.SUPPORTED
                    )
                    and any(
                        item.role is EvidenceRole.NARRATIVE_BINDING
                        and item.source is EvidenceSource.DEBOT
                        and item.exact_ca
                        for item in binding
                    )
                    and any(
                        item.source is EvidenceSource.PRIMARY_ACTOR
                        and item.role in {EvidenceRole.ORIGIN, EvidenceRole.CULTURAL_CONTEXT}
                        for item in binding
                    )
                )
                if not creator_bound and not community_bound:
                    raise ValueError("legitimacy requires primary exact-CA evidence")

    def finding(self, dimension: Dimension) -> DimensionFinding | None:
        target = Dimension(dimension)
        return next((item for item in self.findings if item.dimension is target), None)

    def effective_state(self, dimension: Dimension) -> FindingState:
        finding = self.finding(dimension)
        if finding is None:
            return FindingState.UNKNOWN
        available = usable_ids(self.evidence, self.as_of)
        if finding.state is FindingState.CONTRADICTED:
            return FindingState.CONTRADICTED if available.intersection(finding.contradicts) else FindingState.UNKNOWN
        if finding.state in {FindingState.CONFIRMED, FindingState.SUPPORTED}:
            return finding.state if available.intersection(finding.supports) else FindingState.UNKNOWN
        return finding.state

    def usable_evidence(self, role: EvidenceRole | None = None) -> tuple[EvidenceItem, ...]:
        return tuple(
            item for item in self.evidence
            if item.usable_at(self.as_of) and (role is None or item.role is EvidenceRole(role))
        )

    @property
    def has_capital_confirmation(self) -> bool:
        return bool(self.usable_evidence(EvidenceRole.CAPITAL_CONFIRMATION))
