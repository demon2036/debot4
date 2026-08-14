"""Fast round-robin source for all DeBot BSC launch stages."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from threading import Lock
from time import monotonic

from ..debot.http import DeBotHttp
from ..debot.ranks_client import DeBotRanksClient
from ..debot.ranks_models import RANK_STAGES, RankSnapshot


DEFAULT_MINT_POLL_SECONDS = 0.5


class NarrativeMintMonitor:
    """Poll one DeBot stage per tick without multiplying request pressure."""

    def __init__(
        self,
        client: DeBotRanksClient,
        *,
        poll_seconds: float = DEFAULT_MINT_POLL_SECONDS,
        timer: Callable[[], float] = monotonic,
    ) -> None:
        if not 0.25 <= float(poll_seconds) <= 5:
            raise ValueError("mint poll must be between 0.25 and 5 seconds")
        self.client = client
        self.poll_seconds = float(poll_seconds)
        self.timer = timer
        self._next_poll_at = 0.0
        self._stage_index = 0
        self._status_lock = Lock()
        self.last_stage: str | None = None
        self.last_snapshot_count = 0
        self.last_stage_counts = dict.fromkeys(RANK_STAGES, 0)

    @classmethod
    def from_credentials(
        cls,
        *,
        credential_file: str | Path,
        timeout_seconds: float = 5.0,
        max_response_bytes: int = 2_000_000,
        poll_seconds: float = DEFAULT_MINT_POLL_SECONDS,
    ) -> "NarrativeMintMonitor":
        transport = DeBotHttp(
            credential_file=credential_file,
            timeout_seconds=timeout_seconds,
            max_response_bytes=max_response_bytes,
        )
        return cls(DeBotRanksClient(transport), poll_seconds=poll_seconds)

    def close(self) -> None:
        self.client.transport.close()

    def poll_once(
        self,
        accept: Callable[[tuple[RankSnapshot, ...]], object] | None = None,
    ) -> tuple[RankSnapshot, ...]:
        tick = float(self.timer())
        if tick < self._next_poll_at:
            return ()
        self._next_poll_at = tick + self.poll_seconds
        with self._status_lock:
            stage = RANK_STAGES[self._stage_index % len(RANK_STAGES)]
            self._stage_index += 1
        snapshots = self.client.fetch(stage).snapshots
        with self._status_lock:
            self.last_stage = stage
            self.last_snapshot_count = len(snapshots)
            self.last_stage_counts[stage] = len(snapshots)
        if accept is not None:
            accept(snapshots)
        return snapshots

    def snapshot(self) -> dict[str, object]:
        with self._status_lock:
            return {
                "poll_seconds": self.poll_seconds,
                "stages": list(RANK_STAGES),
                "full_cycle_seconds": self.poll_seconds * len(RANK_STAGES),
                "last_stage": self.last_stage,
                "last_snapshot_count": self.last_snapshot_count,
                "last_stage_counts": dict(self.last_stage_counts),
            }
