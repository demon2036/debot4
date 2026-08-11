"""High-frequency official DeBot polling with causal history bootstrap."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from queue import Full, Queue
from threading import Event
from time import monotonic

from ..domain import DeBotSignal
from ..events import EventLog
from ..ledger import V6Ledger
from ..state import RuntimeState
from .client import DeBotClient, DeBotPage
from .evidence import SOURCE, evidence_id, kol_evidence_metadata


UTC = timezone.utc


class DeBotPoller:
    def __init__(
        self,
        client: DeBotClient,
        ledger: V6Ledger,
        output: Queue[DeBotSignal],
        state: RuntimeState,
        events: EventLog,
        *,
        poll_seconds: float,
        bootstrap_pages: int,
        history_lookback_seconds: float,
    ) -> None:
        self.client = client
        self.ledger = ledger
        self.output = output
        self.state = state
        self.events = events
        self.poll_seconds = poll_seconds
        self.bootstrap_pages = bootstrap_pages
        self.lookback = timedelta(seconds=history_lookback_seconds)
        self.seen: set[str] = set()
        self.watermark: datetime | None = None

    def run(self, stop: Event) -> None:
        try:
            self._bootstrap(stop)
            self.state.update(bootstrapped=True, status="running")
            while not stop.is_set():
                started = monotonic()
                try:
                    page = self.client.fetch_page()
                    self._consume_live(page)
                    elapsed = monotonic() - started
                    self.state.update(
                        last_debot_at=page.fetched_at,
                        last_debot_latency_ms=round(elapsed * 1000, 1),
                        debot_response_bytes=page.bytes_read,
                    )
                except Exception as exc:
                    self.state.error(f"DeBot poll: {type(exc).__name__}: {exc}")
                    self.events.write("debot_poll_error", error=type(exc).__name__, detail=str(exc))
                    elapsed = monotonic() - started
                stop.wait(max(0.0, self.poll_seconds - elapsed))
        finally:
            self.client.close()

    def _bootstrap(self, stop: Event) -> None:
        cursor: str | None = None
        cutoff = datetime.now(UTC) - self.lookback
        pages = 0
        history = 0
        initial_watermark: datetime | None = None
        while pages < self.bootstrap_pages and not stop.is_set():
            page = self.client.fetch_page(cursor)
            pages += 1
            if pages == 1 and page.signals:
                initial_watermark = max(item.event_at for item in page.signals)
            for signal in page.signals:
                self.seen.add(signal.signal_id)
                history += int(self._record_kol(signal))
            oldest = min((item.event_at for item in page.signals), default=page.fetched_at)
            self.state.update(bootstrap_page=pages, bootstrap_kol=history)
            if page.next_cursor is None or oldest < cutoff:
                break
            cursor = page.next_cursor
        self.watermark = initial_watermark or datetime.now(UTC)
        self.events.write(
            "debot_bootstrap_complete", pages=pages, kol_evidence=history,
            watermark=self.watermark,
        )

    def _consume_live(self, page: DeBotPage) -> None:
        ordered = sorted(page.signals, key=lambda item: (item.event_at, item.signal_id))
        for signal in ordered:
            if signal.signal_id in self.seen:
                continue
            self.seen.add(signal.signal_id)
            self._record_kol(signal)
            self.state.increment("signals_seen")
            if self.watermark is not None and signal.event_at <= self.watermark:
                self.events.write(
                    "late_signal_history_only", signal_id=signal.signal_id,
                    event_at=signal.event_at,
                )
                continue
            self._enqueue(signal)
        newest = max((item.event_at for item in page.signals), default=self.watermark)
        if newest is not None and (self.watermark is None or newest > self.watermark):
            self.watermark = newest

    def _record_kol(self, signal: DeBotSignal) -> bool:
        if not signal.kol_buy_qualified:
            return False
        result = self.ledger.record_kol_evidence(
            evidence_id=evidence_id(signal), chain="bsc",
            token_address=signal.token_address, signal_id=signal.signal_id,
            event_at=signal.event_at, available_at=signal.available_at,
            qualified_at=signal.available_at, evidence_uri=signal.evidence_uri,
            source=SOURCE, metadata=kol_evidence_metadata(signal),
        )
        return result.inserted

    def _enqueue(self, signal: DeBotSignal) -> None:
        try:
            self.output.put_nowait(signal)
        except Full:
            self.state.error("decision queue full")
            self.events.write("signal_queue_full", signal_id=signal.signal_id)
            return
        self.state.increment("signals_queued")
        self.events.write(
            "signal_queued", signal_id=signal.signal_id,
            token_address=signal.token_address, kind=signal.signal_kind,
            age_seconds=(datetime.now(UTC) - signal.event_at).total_seconds(),
        )
