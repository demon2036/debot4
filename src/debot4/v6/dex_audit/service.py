"""30-second DEX audit loop, intentionally isolated from BUY decisions."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from threading import Event
from uuid import uuid4

from .coverage import CoverageReader
from .http import DirectJsonClient
from .models import StoredRun
from .providers import fetch_bsc_gainers
from .store import AuditStore


UTC = timezone.utc


def _now_us() -> int:
    return int(datetime.now(UTC).timestamp() * 1_000_000)


class DexAuditService:
    """Records coverage only; it exposes no signal or trading callback."""

    def __init__(
        self,
        *,
        audit_database: str | Path,
        ledger_database: str | Path,
        interval_seconds: float = 30,
        min_liquidity_usd: Decimal = Decimal("25000"),
        client: DirectJsonClient | None = None,
        clock_us: Callable[[], int] = _now_us,
    ) -> None:
        if not 30 <= interval_seconds <= 60:
            raise ValueError("DEX audit interval must be between 30 and 60 seconds")
        self.interval_seconds = float(interval_seconds)
        self.min_liquidity_usd = min_liquidity_usd
        self.client = client or DirectJsonClient()
        self.coverage = CoverageReader(ledger_database)
        self.store = AuditStore(audit_database, clock_us=clock_us)
        self._clock_us = clock_us

    def close(self) -> None:
        self.store.close()

    def __enter__(self) -> DexAuditService:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def refresh_once(self) -> StoredRun:
        as_of_us = self._clock_us()
        board = fetch_bsc_gainers(
            self.client,
            as_of_us=as_of_us,
            limit=20,
            min_liquidity_usd=self.min_liquidity_usd,
        )
        coverage = self.coverage.read(board.rows, as_of_us=board.as_of_us)
        return self.store.append(
            run_id=f"dex-{board.as_of_us}-{uuid4().hex[:12]}",
            board=board,
            coverage=coverage,
        )

    def run_forever(self, stop: Event) -> None:
        while not stop.is_set():
            self.refresh_once()
            stop.wait(self.interval_seconds)
