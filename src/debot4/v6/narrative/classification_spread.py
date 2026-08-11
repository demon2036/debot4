"""Validate narrative spread without treating capital flow as attention."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .domain import EvidenceRole, EvidenceSource
from .evidence import EvidenceItem
from .results import LiveDossierBuild


_NARRATIVE_SOURCES = {
    EvidenceSource.PRIMARY_ACTOR,
    EvidenceSource.OFFICIAL_SITE,
    EvidenceSource.COMMUNITY,
}


@dataclass(frozen=True, slots=True)
class SpreadAssessment:
    evidence: tuple[EvidenceItem, ...]
    independence_groups: tuple[str, ...]

    @property
    def propagated(self) -> bool:
        return bool(self.evidence)

    @property
    def validation_reached(self) -> bool:
        return len(self.independence_groups) >= 2


def assess_spread(
    base: LiveDossierBuild,
    supplied: Iterable[EvidenceItem],
) -> SpreadAssessment:
    """Accept only usable, independently sourced narrative-spread evidence."""

    accepted: dict[str, EvidenceItem] = {}
    for item in (*base.dossier.evidence, *tuple(supplied)):
        if not _eligible(item, base):
            continue
        previous = accepted.get(item.evidence_id)
        if previous is not None and previous != item:
            raise ValueError("conflicting narrative evidence id")
        accepted[item.evidence_id] = item
    evidence = tuple(accepted.values())
    groups = tuple(dict.fromkeys(item.independence_group for item in evidence))
    return SpreadAssessment(evidence, groups)


def _eligible(item: EvidenceItem, base: LiveDossierBuild) -> bool:
    return (
        item.role is EvidenceRole.PROPAGATION
        and item.source in _NARRATIVE_SOURCES
        and bool(item.independence_group.strip())
        and item.token_address in {"", base.dossier.token.address}
        and item.usable_at(base.dossier.as_of)
    )
