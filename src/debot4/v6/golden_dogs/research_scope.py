"""Single authority for the frozen research periods used by all collectors."""

from __future__ import annotations

from datetime import datetime, timezone

from .weekly_scan import ScanWindow, consecutive_windows


UTC = timezone.utc
CHAIN_BOUNDS = {
    "bsc": (
        datetime(2025, 8, 12, tzinfo=UTC),
        datetime(2026, 8, 12, tzinfo=UTC),
    ),
    "robinhood": (
        datetime(2026, 5, 12, tzinfo=UTC),
        datetime(2026, 8, 12, tzinfo=UTC),
    ),
}


def windows_for_chain(chain: str) -> tuple[ScanWindow, ...]:
    try:
        start, end = CHAIN_BOUNDS[chain]
    except KeyError as exc:
        raise ValueError("unsupported research chain") from exc
    return consecutive_windows(start, end)
