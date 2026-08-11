"""Score-free, auditable v6 dossier-build results."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum

from .dossier import NarrativeDossier
from .evidence import EvidenceItem
from .hashing import canonical_sha256, dossier_hash
from .models import CurrentSignalBoundary, RESEARCH_SCHEMA, StatusResearch


class ResearchStatus(str, Enum):
    READY = "READY"
    WAIT = "WAIT"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class BindingAssessment:
    accepted: bool
    reason: str
    addresses: tuple[str, ...]
    semantics: str | None = None
    actor_basis: str | None = None
    evidence: EvidenceItem | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            "addresses": list(self.addresses),
            "semantics": self.semantics,
            "actor_basis": self.actor_basis,
            "evidence_id": None if self.evidence is None else self.evidence.evidence_id,
            "canonicality_claim": "creator_claimed" if self.accepted else None,
            "official_identity_verified": False,
        }


@dataclass(frozen=True, slots=True)
class HistoryItemAudit:
    evidence_identity: str
    signal_id: str
    accepted: bool
    reason: str
    event_time: datetime
    available_at: datetime
    qualified_at: datetime
    inserted_at: datetime
    provider_status: str | None = None
    verification_level: str | None = None
    chain_verified: bool | None = None
    channel: str | None = None
    group: str | None = None
    evidence_kind: str | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "evidence_identity": self.evidence_identity,
            "signal_id": self.signal_id,
            "accepted": self.accepted,
            "reason": self.reason,
            "event_time": self.event_time.isoformat(),
            "available_at": self.available_at.isoformat(),
            "qualified_at": self.qualified_at.isoformat(),
            "inserted_at": self.inserted_at.isoformat(),
            "provider_status": self.provider_status,
            "verification_level": self.verification_level,
            "chain_verified": self.chain_verified,
            "channel": self.channel,
            "group": self.group,
            "evidence_kind": self.evidence_kind,
        }


@dataclass(frozen=True, slots=True)
class HistoricalKolAssessment:
    qualified: bool
    reason: str
    evidence: tuple[EvidenceItem, ...]
    audit: tuple[HistoryItemAudit, ...]
    qualification_kind: str | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "qualified": self.qualified,
            "reason": self.reason,
            "qualification_kind": self.qualification_kind,
            "evidence_ids": [item.evidence_id for item in self.evidence],
            "items": [item.to_payload() for item in self.audit],
            "current_signal_may_self_attest": False,
        }


@dataclass(frozen=True, slots=True)
class NarrativeResearchResult:
    status: ResearchStatus
    reasons: tuple[str, ...]
    decision_time: datetime
    source_research: StatusResearch
    binding: BindingAssessment
    historical_kol: HistoricalKolAssessment
    current_signal: CurrentSignalBoundary | None
    identity: str
    identity_hash: str
    dossier_hash: str

    def expected_identity_hash(self) -> str:
        return canonical_sha256({
            "schema": RESEARCH_SCHEMA,
            "decision_time": self.decision_time.isoformat(),
            "source_research": self.source_research.to_payload(),
            "binding": self.binding.to_payload(),
            "historical_kol": self.historical_kol.to_payload(),
            "current_signal": (
                None if self.current_signal is None else self.current_signal.to_payload()
            ),
            "dossier_hash": self.dossier_hash,
        })

    @property
    def identity_valid(self) -> bool:
        expected = self.expected_identity_hash()
        return self.identity_hash == expected and self.identity == (
            f"{RESEARCH_SCHEMA}:{expected}"
        )

    def to_metadata(self) -> dict[str, object]:
        return {
            "schema": RESEARCH_SCHEMA,
            "status": self.status.value,
            "ready_for_narrative_review": self.status is ResearchStatus.READY,
            "authorizes_trade": False,
            "reasons": list(self.reasons),
            "decision_time": self.decision_time.isoformat(),
            "source_research": self.source_research.to_payload(),
            "binding": self.binding.to_payload(),
            "historical_kol": self.historical_kol.to_payload(),
            "current_signal": (
                None if self.current_signal is None else self.current_signal.to_payload()
            ),
            "identity": self.identity,
            "identity_hash": self.identity_hash,
            "dossier_hash": self.dossier_hash,
        }

    @property
    def metadata(self) -> dict[str, object]:
        return self.to_metadata()


@dataclass(frozen=True, slots=True)
class LiveDossierBuild:
    dossier: NarrativeDossier
    research: NarrativeResearchResult


def bind_research_to_dossier(
    research: NarrativeResearchResult,
    dossier: NarrativeDossier,
) -> NarrativeResearchResult:
    """Bind immutable source research to a same-cutoff enriched dossier."""

    if research.source_research.token != dossier.token:
        raise ValueError("research and dossier token must match")
    if research.decision_time != dossier.as_of:
        raise ValueError("research and dossier must share an exact cutoff")
    draft = replace(
        research,
        dossier_hash=dossier_hash(dossier),
        identity="pending",
        identity_hash="pending",
    )
    digest = draft.expected_identity_hash()
    return replace(
        draft,
        identity=f"{RESEARCH_SCHEMA}:{digest}",
        identity_hash=digest,
    )
