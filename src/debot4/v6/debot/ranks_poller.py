"""Round-robin DeBot ranks polling and historical KOL proxy evidence."""

from __future__ import annotations

from threading import Event
from time import monotonic

from ..events import EventLog
from ..identity import json_safe, stable_id
from ..ledger import V6Ledger
from ..state import RuntimeState
from .ranks_client import DeBotRanksClient
from .ranks_models import RANK_STAGES, RankKolIncrease, RankPage
from .ranks_state import RankState


SOURCE = "debot:bsc:ranks-kol-increase"


class DeBotRanksPoller:
    def __init__(
        self, client: DeBotRanksClient, ledger: V6Ledger, rank_state: RankState,
        runtime_state: RuntimeState, events: EventLog, *, poll_seconds: float,
    ) -> None:
        self.client = client
        self.ledger = ledger
        self.ranks = rank_state
        self.runtime = runtime_state
        self.events = events
        self.poll_seconds = poll_seconds

    def run(self, stop: Event) -> None:
        index = 0
        while not stop.is_set():
            started = monotonic()
            stage = RANK_STAGES[index % len(RANK_STAGES)]
            index += 1
            try:
                page = self.client.fetch(stage)
                increases = self._consume(page)
                self.runtime.update(
                    last_ranks_at=page.fetched_at,
                    last_ranks_stage=stage,
                    last_ranks_latency_ms=round((monotonic() - started) * 1_000, 1),
                    rank_tokens=len(page.snapshots),
                )
                if increases:
                    self.runtime.increment("rank_kol_increases", increases)
            except Exception as exc:
                self.runtime.error(f"DeBot ranks: {type(exc).__name__}: {exc}")
                self.events.write(
                    "debot_ranks_error", error=type(exc).__name__, detail=str(exc),
                )
            elapsed = monotonic() - started
            stop.wait(max(0.0, self.poll_seconds - elapsed))

    def _consume(self, page: RankPage) -> int:
        changes = [change for item in page.snapshots if (change := self.ranks.observe(item))]
        self.ranks.save()
        for change in changes:
            self._record(change)
        return len(changes)

    def _record(self, change: RankKolIncrease) -> None:
        item = change.snapshot
        event_key = (
            item.token_address, item.stage, int(item.fetched_at.timestamp() * 1_000),
            change.previous_kols, item.kols,
        )
        signal_id = stable_id("rank-signal", *event_key)
        result = self.ledger.record_kol_evidence(
            evidence_id=stable_id("rank-kol", *event_key),
            chain="bsc", token_address=item.token_address,
            signal_id=signal_id, event_at=item.fetched_at,
            available_at=item.fetched_at, qualified_at=item.fetched_at,
            source=SOURCE,
            evidence_uri=f"https://debot.ai/token/bsc/{item.token_address}",
            metadata=json_safe({
                "schema": "debot_ranks_kol_increase.v1",
                "claim": "historical_kol_participation_proxy",
                "verification_level": "provider_aggregate_asserted",
                "chain_verified": False,
                "stage": item.stage,
                "previous_kols": change.previous_kols,
                "current_kols": item.kols,
                "increase": change.increase,
                "previous_aliases": change.previous_aliases,
                "current_aliases": item.kol_aliases,
                "provider_fdv_usd": item.provider_fdv_usd,
            }),
        )
        if result.inserted:
            self.events.write(
                "rank_kol_evidence", token_address=item.token_address,
                previous=change.previous_kols, current=item.kols, stage=item.stage,
            )
