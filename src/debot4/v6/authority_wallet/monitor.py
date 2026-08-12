"""Idempotent ingestion boundary for already-verified wallet receipts."""

from __future__ import annotations

from dataclasses import dataclass

from ..explosion import ExplosionEvent, ExplosionEventStore
from .rules import AuthorityWalletAction


@dataclass(slots=True)
class AuthorityWalletMonitor:
    events: ExplosionEventStore

    def ingest(self, action: AuthorityWalletAction) -> ExplosionEvent | None:
        event = action.event()
        return event if self.events.append(event) else None
