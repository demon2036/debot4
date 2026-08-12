"""Deterministic UTC windows and prompts for Grok discovery-only sweeps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib


UTC = timezone.utc
WEEK = timedelta(days=7)


@dataclass(frozen=True, slots=True)
class ScanWindow:
    start: datetime
    end_exclusive: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end_exclusive.tzinfo is None:
            raise ValueError("weekly scan bounds must be timezone-aware")
        if self.end_exclusive <= self.start or self.end_exclusive - self.start > WEEK:
            raise ValueError("scan window must be positive and at most seven days")

    @property
    def key(self) -> str:
        return f"{_day(self.start)}_{_day(self.end_exclusive)}"


def consecutive_windows(start: datetime, end_exclusive: datetime) -> tuple[ScanWindow, ...]:
    if start.tzinfo is None or end_exclusive.tzinfo is None or start >= end_exclusive:
        raise ValueError("valid timezone-aware scan bounds are required")
    cursor = start.astimezone(UTC)
    end = end_exclusive.astimezone(UTC)
    result = []
    while cursor < end:
        boundary = min(cursor + WEEK, end)
        result.append(ScanWindow(cursor, boundary))
        cursor = boundary
    return tuple(result)


def window_for_timestamp(
    windows: tuple[ScanWindow, ...], timestamp: int,
) -> ScanWindow | None:
    """Return the sole fixed window containing a Unix timestamp."""

    matches = tuple(
        item for item in windows
        if int(item.start.timestamp()) <= timestamp < int(item.end_exclusive.timestamp())
    )
    if len(matches) > 1:
        raise ValueError("scan windows overlap")
    return matches[0] if matches else None


def sweep_prompts(window: ScanWindow) -> tuple[str, ...]:
    bounds = (
        f"UTC [{window.start.isoformat()}, {window.end_exclusive.isoformat()})"
    )
    common = f"""
Carpet-scan BNB Smart Chain meme tokens first launched or first traded in {bounds}.
A lead needs an exact 0x contract address and evidence it reached at least USD 500,000
market cap or FDV. We independently verify every claim, so do not infer an address from
a ticker. Return direct URLs and dates. A DeBot or GMGN KOL-buy record is required for
final eligibility; max_kols counts, X posts, transfers, and smart-money labels alone do
not prove a KOL bought. Label uncertainty and return an empty list if no evidence exists.
""".strip()
    return (
        common + "\nSearch broadly across launchpads, DEX trackers, archives, and news. List every candidate you can substantiate.",
        common + "\nSearch specifically DeBot and GMGN KOL-buy surfaces, screenshots/posts, wallet aliases, buy times, transaction hashes, and exact wallets.",
        common + "\nSearch X for earliest calls and post-pump reviews, then look for omitted BSC runners and same-ticker competing contracts.",
    )


def prompt_sha256(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _day(value: datetime) -> str:
    return value.astimezone(UTC).date().isoformat()
