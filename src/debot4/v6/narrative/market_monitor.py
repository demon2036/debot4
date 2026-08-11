"""Self-throttled BSC anomaly source independent of social collectors."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Protocol

from ..dex_audit.http import DirectJsonClient
from ..dex_audit.models import Board
from ..dex_audit.providers import fetch_bsc_gainers
from ..identity import utc_datetime, utc_now
from .market_signal import MarketAnomaly, MarketQualityPolicy
from .market_state import MarketAnomalyState


class BoardFetcher(Protocol):
    def __call__(
        self, client: DirectJsonClient, *, as_of_us: int, limit: int = 20
    ) -> Board: ...


class MarketAnomalyMonitor:
    """Poll exact 1h rankings and emit each CA/stage/day at most once."""

    def __init__(
        self,
        checkpoint: str | Path,
        *,
        client: DirectJsonClient | None = None,
        policy: MarketQualityPolicy | None = None,
        poll_seconds: float = 5.0,
        fetcher: BoardFetcher = fetch_bsc_gainers,
        clock: Callable[[], datetime] = utc_now,
        timer: Callable[[], float] = monotonic,
    ) -> None:
        if not 0.5 <= poll_seconds <= 15:
            raise ValueError("market poll must be between 0.5 and 15 seconds")
        self.state = MarketAnomalyState(checkpoint)
        self.client = client or DirectJsonClient()
        self.policy = policy or MarketQualityPolicy()
        self.poll_seconds = poll_seconds
        self.fetcher = fetcher
        self.clock = clock
        self.timer = timer
        self._next_due = 0.0
        self.last_board: Board | None = None
        self.last_error_type: str | None = None
        self.last_rejection_counts: dict[str, int] = {}

    def poll_once(
        self,
        accept: Callable[[tuple[MarketAnomaly, ...]], object] | None = None,
    ) -> tuple[MarketAnomaly, ...]:
        tick = self.timer()
        if tick < self._next_due:
            return ()
        self._next_due = tick + self.poll_seconds
        now = utc_datetime(self.clock())
        try:
            board = self.fetcher(
                self.client, as_of_us=int(now.timestamp() * 1_000_000), limit=100
            )
            selection = self.policy.select(board)
        except Exception as exc:
            self.last_error_type = type(exc).__name__
            return ()
        self.last_board = board
        self.last_error_type = None
        counts: dict[str, int] = {}
        for item in selection.rejections:
            counts[item.reason] = counts.get(item.reason, 0) + 1
        self.last_rejection_counts = counts
        fresh = tuple(
            item for item in selection.anomalies
            if not self.state.contains(item.anomaly_id)
        )
        if accept is not None:
            accept(fresh)
        if fresh:
            self.state.mark(tuple(item.anomaly_id for item in fresh), now)
        return fresh
