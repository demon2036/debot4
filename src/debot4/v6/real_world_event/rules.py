"""Real-world narrative observations remain research candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..explosion import ExplosionCategory, ExplosionEvent


@dataclass(frozen=True, slots=True)
class RealWorldObservation:
    subject: str
    event_kind: str
    actor_id: str
    actor_role: str
    occurred_at: datetime
    first_seen_at: datetime
    source_url: str
    evidence_hash: str
    confidence: str = "reported"

    def event(self) -> ExplosionEvent:
        return ExplosionEvent(
            category=ExplosionCategory.REAL_WORLD_EVENT,
            subtype=self.event_kind,
            occurred_at=self.occurred_at,
            first_seen_at=self.first_seen_at,
            subject=self.subject,
            actor_id=self.actor_id,
            actor_role=self.actor_role,
            source_url=self.source_url,
            evidence_hash=self.evidence_hash,
            previous={},
            current={"research_candidate": True},
            confidence=self.confidence,
        )
