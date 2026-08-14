"""Bounded application workflow for one fixed seven-day OHLC assessment."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from decimal import Decimal
import time
from typing import Callable, Iterable, Mapping

from .debot_public import PublicDeBotClient
from .models import Candle, EvidenceReceipt, Observation, TokenSeed
from .rules import GOLD_MIN_PEAK_FDV_USD, analyze_market, observation_from_points
from .weekly_scan import ScanWindow, window_for_timestamp


@dataclass(frozen=True, slots=True)
class MarketAuditResult:
    observations: tuple[Observation, ...]
    errors: tuple[tuple[str, str, str], ...]


@dataclass(frozen=True, slots=True)
class WindowBars:
    candles: tuple[Candle, ...]
    total_supply: Decimal | None
    receipts: tuple[EvidenceReceipt, ...]
    coverage_complete: bool


def audit_markets(
    client_factory: Callable[[], PublicDeBotClient],
    seeds: Iterable[TokenSeed],
    windows_by_chain: Mapping[str, tuple[ScanWindow, ...]],
    *,
    workers: int = 8,
    item_attempts: int = 2,
) -> MarketAuditResult:
    """Measure only the fixed window containing each token's creation time."""

    if not 1 <= item_attempts <= 5:
        raise ValueError("market item attempts must be between one and five")

    observations: list[Observation] = []
    errors: list[tuple[str, str, str]] = []

    def measure(seed: TokenSeed) -> Observation:
        window = window_for_timestamp(
            windows_by_chain.get(seed.chain, ()), seed.created_at,
        )
        if window is None:
            raise ValueError("token has no assigned market window")
        start = int(window.start.timestamp())
        end = int(window.end_exclusive.timestamp())
        with client_factory() as client:
            daily = client.fetch_market(seed.chain, seed.address)
            rough = analyze_market(
                seed,
                daily,
                window_start=start,
                window_end_exclusive=end,
                precision="window_daily_open_and_high",
            )
            if not _needs_refinement(rough):
                return rough
            five_minute = fetch_window_bars(client, seed, start, end, 300)
            if not five_minute.coverage_complete or not five_minute.candles:
                return _incomplete_refinement(rough)
            traded = tuple(
                bar for bar in five_minute.candles if bar.open > 0 and bar.high > 0
            )
            if not traded:
                return _incomplete_refinement(rough)
            first_five = traded[0]
            first_page = client.fetch_market(
                seed.chain,
                seed.address,
                interval_seconds=60,
                end=min(end, first_five.time + 600),
            )
            first_minutes = tuple(
                bar for bar in first_page.candles
                if start <= bar.time < end and bar.open > 0
            )
            first = first_minutes[0] if first_minutes else first_five
            peak = max(traded, key=lambda bar: (bar.high, -bar.time))
            supply = five_minute.total_supply or rough.total_supply
            if supply is None:
                return rough
            receipts = (daily.receipt, *five_minute.receipts, first_page.receipt)
            return observation_from_points(
                seed,
                first,
                peak,
                supply,
                supply_source=rough.supply_source or "rank_creation_supply",
                precision="window_first_1m_open_peak_5m_high",
                receipts=receipts,
                window_start=start,
                window_end_exclusive=end,
            )

    def one(seed: TokenSeed) -> Observation:
        last_error: Exception | None = None
        for attempt in range(item_attempts):
            try:
                return measure(seed)
            except Exception as exc:
                last_error = exc
                if attempt + 1 < item_attempts:
                    time.sleep(0.25 * (2**attempt))
        assert last_error is not None
        raise last_error

    with ThreadPoolExecutor(max_workers=workers) as executor:
        jobs = {executor.submit(one, seed): seed for seed in seeds}
        for job in as_completed(jobs):
            seed = jobs[job]
            try:
                observations.append(job.result())
            except Exception as exc:
                errors.append((seed.chain, seed.address, type(exc).__name__))
    return MarketAuditResult(
        tuple(sorted(observations, key=lambda x: (x.chain, x.created_at, x.address))),
        tuple(sorted(errors)),
    )


def fetch_window_bars(
    client: PublicDeBotClient,
    seed: TokenSeed,
    start: int,
    end_exclusive: int,
    interval_seconds: int,
    *,
    max_pages: int = 8,
) -> WindowBars:
    """Page backwards until the complete bounded interval is covered."""

    if not start <= seed.created_at < end_exclusive:
        raise ValueError("token is outside requested market range")
    if not 1 <= max_pages <= 64:
        raise ValueError("market page limit must be between one and 64")
    cursor = end_exclusive
    candles: dict[int, Candle] = {}
    receipts: list[EvidenceReceipt] = []
    supplies: list[Decimal] = []
    complete = False
    for _ in range(max_pages):
        page = client.fetch_market(
            seed.chain, seed.address,
            interval_seconds=interval_seconds, limit=1_000, end=cursor,
        )
        receipts.append(page.receipt)
        if page.total_supply is not None:
            supplies.append(page.total_supply)
        rows = tuple(bar for bar in page.candles if start <= bar.time < end_exclusive)
        candles.update((bar.time, bar) for bar in rows)
        if not page.candles:
            complete = True
            break
        earliest = min(bar.time for bar in page.candles)
        if earliest <= start or earliest <= seed.created_at:
            complete = True
            break
        if earliest >= cursor:
            break
        cursor = earliest
    supply = supplies[0] if supplies else None
    if any(item != supply for item in supplies):
        raise ValueError("market pages disagree on current total supply")
    return WindowBars(
        tuple(candles[key] for key in sorted(candles)),
        supply,
        tuple(receipts),
        complete,
    )


def _needs_refinement(observation: Observation) -> bool:
    return (
        observation.status == "complete"
        and observation.approx_peak_fdv_usd is not None
        and observation.approx_peak_fdv_usd >= GOLD_MIN_PEAK_FDV_USD
    )


def _incomplete_refinement(rough: Observation) -> Observation:
    from dataclasses import replace

    return replace(
        rough,
        meets_peak_threshold=False,
        precision="window_5m_history_incomplete",
        status="window_refinement_incomplete",
    )
