"""Thread-safe persistence accounting for independently located Exact CAs."""

from __future__ import annotations

from collections.abc import Iterable
from threading import Lock

from .mint_location import MintLocation
from .mint_location_store import MintLocationStore, MintLocationWrite


class MintCollectionPipeline:
    """Own raw-location writes and metrics, separate from narrative queueing."""

    def __init__(self, store: MintLocationStore | None) -> None:
        self.store = store
        self._lock = Lock()
        self._debot_write = MintLocationWrite()
        self._chain_write = MintLocationWrite()
        self._hard_bindings_queued = 0

    def reset_cycle_source(self, *, chain: bool) -> None:
        with self._lock:
            if chain:
                self._chain_write = MintLocationWrite()
            else:
                self._debot_write = MintLocationWrite()

    def record(
        self, locations: Iterable[MintLocation], *, chain: bool,
    ) -> None:
        if self.store is None:
            raise RuntimeError("mint location storage is unavailable")
        write = self.store.record(locations)
        with self._lock:
            current = self._chain_write if chain else self._debot_write
            combined = MintLocationWrite(
                current.inserted + write.inserted,
                current.enriched + write.enriched,
                current.unchanged + write.unchanged,
            )
            if chain:
                self._chain_write = combined
            else:
                self._debot_write = combined

    def record_hard_bindings(self, count: int) -> None:
        if count <= 0:
            return
        with self._lock:
            self._hard_bindings_queued += count

    def cycle_inserted(self) -> int:
        with self._lock:
            return self._debot_write.inserted + self._chain_write.inserted

    def snapshot(self, accepted_signals: int) -> dict[str, object]:
        with self._lock:
            bindings = self._hard_bindings_queued
        raw = (
            {"configured": False, "observations": 0, "unique_exact_cas": 0}
            if self.store is None
            else {"configured": True, **self.store.snapshot()}
        )
        return {
            "narrative_signals_queued": max(0, accepted_signals - bindings),
            "mint_locations": raw,
            "hard_catalyst_bindings_queued": bindings,
            "raw_location_queues_research": False,
            "raw_location_authorizes_trade": False,
        }
