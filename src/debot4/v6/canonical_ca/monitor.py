"""Persist competing-CA decisions and emit only newly selected leaders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json

from ..explosion import ExplosionEvent, ExplosionEventStore, JsonEvidenceStateStore
from .rules import (
    CaCandidate,
    CanonicalDecision,
    leader_change_event,
    resolve_canonical_ca,
)


@dataclass(slots=True)
class CanonicalCaMonitor:
    snapshots: JsonEvidenceStateStore
    events: ExplosionEventStore

    def evaluate(
        self,
        candidates: tuple[CaCandidate, ...],
        *,
        subject: str,
        actor_id: str,
        actor_role: str,
        occurred_at: datetime,
        first_seen_at: datetime,
        source_url: str,
        evidence_hash: str,
        chain: str,
    ) -> ExplosionEvent | None:
        key = f"{chain}|{subject}"
        previous = _decode(self.snapshots.load(key))
        current = resolve_canonical_ca(candidates)
        event = leader_change_event(
            previous,
            current,
            subject=subject,
            actor_id=actor_id,
            actor_role=actor_role,
            occurred_at=occurred_at,
            first_seen_at=first_seen_at,
            source_url=source_url,
            evidence_hash=evidence_hash,
            chain=chain,
        )
        inserted = event is not None and self.events.append(event)
        self.snapshots.save(key, _encode(current))
        return event if inserted else None


def _encode(item: CanonicalDecision) -> dict[str, object]:
    return {
        "status": item.status,
        "leader": item.leader,
        "scores_json": json.dumps(item.scores, separators=(",", ":")),
    }


def _decode(row: dict[str, object] | None) -> CanonicalDecision:
    if row is None:
        return CanonicalDecision("unresolved", "", ())
    try:
        raw_scores = json.loads(str(row["scores_json"]))
        scores = tuple((str(address), int(score)) for address, score in raw_scores)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("canonical CA state is invalid") from exc
    return CanonicalDecision(str(row["status"]), str(row["leader"]), scores)
