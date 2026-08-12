"""Persist adverse-state history and emit evidence-backed resolution changes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..explosion import ExplosionEvent, ExplosionEventStore, JsonEvidenceStateStore
from .rules import RiskObservation, RiskState, risk_transition


@dataclass(slots=True)
class RiskResolutionMonitor:
    snapshots: JsonEvidenceStateStore
    events: ExplosionEventStore

    def observe(self, current: RiskObservation) -> ExplosionEvent | None:
        key = f"{current.chain}|{current.token_address}|{current.subject}"
        previous = _decode(self.snapshots.load(key))
        event = risk_transition(previous, current)
        inserted = event is not None and self.events.append(event)
        self.snapshots.save(key, _encode(current))
        return event if inserted else None


def _encode(item: RiskObservation) -> dict[str, object]:
    return {
        "subject": item.subject,
        "actor_id": item.actor_id,
        "actor_role": item.actor_role,
        "state": item.state.value,
        "reason": item.reason,
        "occurred_at": item.occurred_at.isoformat(),
        "first_seen_at": item.first_seen_at.isoformat(),
        "source_url": item.source_url,
        "evidence_hash": item.evidence_hash,
        "chain": item.chain,
        "token_address": item.token_address,
    }


def _decode(row: dict[str, object] | None) -> RiskObservation | None:
    if row is None:
        return None
    return RiskObservation(
        subject=str(row["subject"]),
        actor_id=str(row["actor_id"]),
        actor_role=str(row["actor_role"]),
        state=RiskState(str(row["state"])),
        reason=str(row["reason"]),
        occurred_at=datetime.fromisoformat(str(row["occurred_at"])),
        first_seen_at=datetime.fromisoformat(str(row["first_seen_at"])),
        source_url=str(row["source_url"]),
        evidence_hash=str(row["evidence_hash"]),
        chain=str(row["chain"]),
        token_address=str(row["token_address"]),
    )
