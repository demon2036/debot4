"""One-shot official resource monitor; scheduling is an outer concern."""

from __future__ import annotations

from dataclasses import dataclass

from ..explosion import ExplosionEvent, ExplosionEventStore
from .client import PublicResourceClient, PublicResourceTarget
from .rules import product_diff_events
from .store import JsonPublicResourceSnapshotStore


@dataclass(slots=True)
class PublicResourceMonitor:
    client: PublicResourceClient
    snapshots: JsonPublicResourceSnapshotStore
    events: ExplosionEventStore

    def poll(self, target: PublicResourceTarget) -> tuple[ExplosionEvent, ...]:
        current = self.client.fetch(target)
        previous = self.snapshots.load(target.resource_id)
        if previous is None:
            self.snapshots.save(current)
            return ()
        found = product_diff_events(previous, current)
        for event in found:
            self.events.append(event)
        self.snapshots.save(current)
        return found
