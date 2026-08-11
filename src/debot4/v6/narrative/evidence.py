"""Point-in-time v6 evidence with strict role boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .domain import EvidenceRole, EvidenceScope, EvidenceSource
from .models import aware_utc


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    evidence_id: str
    source: EvidenceSource
    role: EvidenceRole
    claim: str
    published_at: datetime
    first_seen_at: datetime
    captured_at: datetime
    token_address: str = ""
    source_actor: str = ""
    status_id: str = ""
    exact_ca: bool = False
    independence_group: str = ""
    scope: EvidenceScope = EvidenceScope.LIVE_ELIGIBLE

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", EvidenceSource(self.source))
        object.__setattr__(self, "role", EvidenceRole(self.role))
        object.__setattr__(self, "scope", EvidenceScope(self.scope))
        object.__setattr__(self, "token_address", self.token_address.strip().lower())
        for name in ("published_at", "first_seen_at", "captured_at"):
            object.__setattr__(self, name, aware_utc(getattr(self, name), name))
        if not self.evidence_id.strip() or not self.claim.strip():
            raise ValueError("evidence_id and claim are required")
        if self.first_seen_at < self.published_at:
            raise ValueError("first_seen_at cannot predate published_at")
        if self.captured_at < self.first_seen_at:
            raise ValueError("captured_at cannot predate first_seen_at")
        if self.source is EvidenceSource.DEBOT and self.role in {
            EvidenceRole.ORIGIN,
            EvidenceRole.TOKEN_BINDING,
        }:
            raise ValueError("DeBot metadata cannot prove origin or token binding")
        if self.source is EvidenceSource.DEBOT and (not self.token_address or not self.exact_ca):
            raise ValueError("DeBot evidence must bind an exact token")
        if self.role is EvidenceRole.TOKEN_BINDING and (not self.exact_ca or not self.token_address):
            raise ValueError("token binding requires an exact token address")
        if self.role is EvidenceRole.NARRATIVE_BINDING and (
            not self.exact_ca or not self.token_address
        ):
            raise ValueError("narrative binding requires an exact token address")

    def usable_at(self, as_of: datetime) -> bool:
        cutoff = aware_utc(as_of, "as_of")
        return (
            self.scope is not EvidenceScope.POSTMORTEM_ONLY
            and self.published_at <= cutoff
            and self.first_seen_at <= cutoff
            and self.captured_at <= cutoff
        )


def usable_ids(items: tuple[EvidenceItem, ...], as_of: datetime) -> frozenset[str]:
    return frozenset(item.evidence_id for item in items if item.usable_at(as_of))
