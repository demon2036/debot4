"""Fast DeBot new-creation source; matching remains a separate domain boundary."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from time import monotonic

from ..debot.http import DeBotHttp
from ..debot.ranks_client import DeBotRanksClient
from ..debot.ranks_models import RankSnapshot


DEFAULT_MINT_POLL_SECONDS = 0.5


class NarrativeMintMonitor:
    """Poll only new BSC creations without persisting bulk provider responses."""

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
        self.last_snapshot_count = 0

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
        snapshots = self.client.fetch("new").snapshots
        self.last_snapshot_count = len(snapshots)
        if accept is not None:
            accept(snapshots)
        return snapshots
