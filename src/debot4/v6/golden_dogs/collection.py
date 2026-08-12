"""Application orchestration for complete capped-rank universe traversal."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable

from .debot_parser import merge_seeds, parse_seed
from .debot_public import PublicDeBotClient
from .models import EvidenceReceipt, TokenSeed


UTC = timezone.utc


@dataclass(frozen=True, slots=True)
class SaturatedSlice:
    chain: str
    source: str
    min_age_minutes: int
    max_age_minutes: int
    rows_returned: int


@dataclass(frozen=True, slots=True)
class UniverseResult:
    tokens: tuple[TokenSeed, ...]
    receipts: tuple[EvidenceReceipt, ...]
    saturated_slices: tuple[SaturatedSlice, ...]

    @property
    def coverage_complete(self) -> bool:
        return not self.saturated_slices


def collect_source(
    client: PublicDeBotClient,
    chain: str,
    source: str,
    max_age_minutes: int,
    *,
    page_limit: int = 100,
    min_slice_minutes: int = 1,
) -> UniverseResult:
    """Split capped age windows until every terminal response is below limit."""

    pending = [(0, max_age_minutes)]
    tokens: dict[tuple[str, str], TokenSeed] = {}
    receipts: list[EvidenceReceipt] = []
    saturated: list[SaturatedSlice] = []
    while pending:
        low, high = pending.pop()
        page = client.fetch_rank_page(chain, source, low, high, limit=page_limit)
        receipts.append(page.receipt)
        if len(page.rows) >= page_limit and high - low > min_slice_minutes:
            midpoint = low + (high - low) // 2
            pending.extend(((low, midpoint), (midpoint, high)))
            continue
        if len(page.rows) >= page_limit:
            saturated.append(SaturatedSlice(chain, source, low, high, len(page.rows)))
        for row in page.rows:
            seed = parse_seed(row, source)
            key = (seed.chain, seed.address)
            if key in tokens:
                seed = merge_seeds(tokens[key], seed)
            tokens[key] = seed
    return UniverseResult(
        tokens=tuple(sorted(tokens.values(), key=lambda x: (x.created_at, x.address))),
        receipts=tuple(receipts),
        saturated_slices=tuple(saturated),
    )


def collect_universe(
    client_factory: Callable[[], PublicDeBotClient],
    chain: str,
    sources: Iterable[str],
    start_at: datetime,
    end_at: datetime,
    *,
    workers: int = 6,
) -> UniverseResult:
    """Collect each launch source independently and filter to fixed UTC bounds."""

    if start_at.tzinfo is None or end_at.tzinfo is None or start_at >= end_at:
        raise ValueError("fixed UTC collection bounds are required")
    now = datetime.now(UTC)
    max_age = int((now - start_at.astimezone(UTC)).total_seconds() // 60) + 2
    start_ts, end_ts = int(start_at.timestamp()), int(end_at.timestamp())
    results: list[UniverseResult] = []

    def one(source: str) -> UniverseResult:
        with client_factory() as local_client:
            return collect_source(local_client, chain, source, max_age)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        jobs = {executor.submit(one, source): source for source in sources}
        for job in as_completed(jobs):
            results.append(job.result())

    tokens: dict[tuple[str, str], TokenSeed] = {}
    for result in results:
        for seed in result.tokens:
            if not start_ts <= seed.created_at < end_ts:
                continue
            key = (seed.chain, seed.address)
            tokens[key] = merge_seeds(tokens[key], seed) if key in tokens else seed
    return UniverseResult(
        tokens=tuple(sorted(tokens.values(), key=lambda x: (x.created_at, x.address))),
        receipts=tuple(receipt for result in results for receipt in result.receipts),
        saturated_slices=tuple(item for result in results for item in result.saturated_slices),
    )
