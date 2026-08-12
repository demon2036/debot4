"""Persist distribution observations and emit actual state transitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..explosion import ExplosionEvent, ExplosionEventStore, JsonEvidenceStateStore
from .rules import AccessObservation, AccessState, access_transition


@dataclass(slots=True)
class DistributionAccessMonitor:
    snapshots: JsonEvidenceStateStore
    events: ExplosionEventStore

    def observe(self, current: AccessObservation) -> ExplosionEvent | None:
        key = f"{current.venue}|{current.market}"
        previous = _decode(self.snapshots.load(key))
        event = access_transition(previous, current)
        inserted = event is not None and self.events.append(event)
        self.snapshots.save(key, _encode(current))
        return event if inserted else None


def _encode(item: AccessObservation) -> dict[str, object]:
    return {
        "venue": item.venue,
        "market": item.market,
        "actor_id": item.actor_id,
        "actor_role": item.actor_role,
        "state": int(item.state),
        "occurred_at": item.occurred_at.isoformat(),
        "first_seen_at": item.first_seen_at.isoformat(),
        "source_url": item.source_url,
        "evidence_hash": item.evidence_hash,
        "chain": item.chain,
        "token_address": item.token_address,
    }


def _decode(row: dict[str, object] | None) -> AccessObservation | None:
    if row is None:
        return None
    return AccessObservation(
        venue=str(row["venue"]),
        market=str(row["market"]),
        actor_id=str(row["actor_id"]),
        actor_role=str(row["actor_role"]),
        state=AccessState(int(row["state"])),
        occurred_at=datetime.fromisoformat(str(row["occurred_at"])),
        first_seen_at=datetime.fromisoformat(str(row["first_seen_at"])),
        source_url=str(row["source_url"]),
        evidence_hash=str(row["evidence_hash"]),
        chain=str(row["chain"]),
        token_address=str(row["token_address"]),
    )
