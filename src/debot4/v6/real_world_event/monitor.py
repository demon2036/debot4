"""Idempotent ingestion boundary for reviewed real-world source events."""

from __future__ import annotations

from dataclasses import dataclass

from ..explosion import ExplosionEvent, ExplosionEventStore
from .rules import RealWorldObservation


@dataclass(slots=True)
class RealWorldEventMonitor:
    events: ExplosionEventStore

    def ingest(self, observation: RealWorldObservation) -> ExplosionEvent | None:
        event = observation.event()
        return event if self.events.append(event) else None
