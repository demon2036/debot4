"""Pure golden-dog measurements; no network, persistence, or buy decisions."""

from __future__ import annotations

from decimal import Decimal

from .models import Candle, MarketTrace, Observation, TokenSeed


TIER_MULTIPLES = (Decimal("3"), Decimal("10"), Decimal("30"), Decimal("100"))
GOLD_MIN_PEAK_FDV_USD = Decimal("500000")


def analyze_market(
    seed: TokenSeed,
    trace: MarketTrace,
    *,
    window_start: int,
    window_end_exclusive: int,
    precision: str = "daily",
) -> Observation:
    """Measure the first trade and peak inside one explicit seven-day window."""

    _validate_window(seed, window_start, window_end_exclusive)
    traded = tuple(
        bar for bar in trace.candles
        if window_start <= bar.time < window_end_exclusive
        and bar.open > 0 and bar.high > 0
    )
    if not traded:
        return _incomplete(
            seed, trace, "no_market_history", precision,
            window_start, window_end_exclusive,
        )
    first = traded[0]
    peak = max(traded, key=lambda bar: (bar.high, -bar.time))
    supply = trace.total_supply or seed.rank_supply
    supply_source = "market_current_total_supply" if trace.total_supply else "rank_creation_supply"
    if supply is None:
        return _incomplete(
            seed, trace, "missing_supply", precision,
            window_start, window_end_exclusive,
        )
    return observation_from_points(
        seed,
        first,
        peak,
        supply,
        supply_source=supply_source,
        precision=precision,
        receipts=(trace.receipt,),
        window_start=window_start,
        window_end_exclusive=window_end_exclusive,
    )


def observation_from_points(
    seed: TokenSeed,
    first: Candle,
    peak: Candle,
    supply: Decimal,
    *,
    supply_source: str,
    precision: str,
    receipts: tuple,
    window_start: int,
    window_end_exclusive: int,
) -> Observation:
    _validate_window(seed, window_start, window_end_exclusive)
    if first.open <= 0 or peak.high <= 0 or supply <= 0:
        raise ValueError("market points and supply must be positive")
    if not (
        window_start <= first.time < window_end_exclusive
        and window_start <= peak.time < window_end_exclusive
    ):
        raise ValueError("market points must fall inside the seven-day window")
    multiple = peak.high / first.open
    initial_fdv = first.open * supply
    peak_fdv = peak.high * supply
    tiers = tuple(f"{int(value)}x" for value in TIER_MULTIPLES if multiple >= value)
    meets_peak_threshold = peak_fdv >= GOLD_MIN_PEAK_FDV_USD
    return Observation(
        chain=seed.chain,
        address=seed.address,
        name=seed.name,
        symbol=seed.symbol,
        launchpad=seed.launchpad,
        created_at=seed.created_at,
        window_start=window_start,
        window_end_exclusive=window_end_exclusive,
        first_trade_at=first.time,
        first_price_usd=first.open,
        peak_at=peak.time,
        peak_price_usd=peak.high,
        total_supply=supply,
        supply_source=supply_source,
        initial_fdv_usd=initial_fdv,
        approx_peak_fdv_usd=peak_fdv,
        peak_multiple=multiple,
        tiers=tiers,
        meets_peak_threshold=meets_peak_threshold,
        current_kols=seed.current_kols,
        max_kols=seed.max_kols,
        precision=precision,
        status="complete",
        receipts=receipts,
    )


def _incomplete(
    seed: TokenSeed,
    trace: MarketTrace,
    status: str,
    precision: str,
    window_start: int,
    window_end_exclusive: int,
) -> Observation:
    return Observation(
        chain=seed.chain,
        address=seed.address,
        name=seed.name,
        symbol=seed.symbol,
        launchpad=seed.launchpad,
        created_at=seed.created_at,
        window_start=window_start,
        window_end_exclusive=window_end_exclusive,
        first_trade_at=None,
        first_price_usd=None,
        peak_at=None,
        peak_price_usd=None,
        total_supply=trace.total_supply or seed.rank_supply,
        supply_source=(
            "market_current_total_supply" if trace.total_supply else
            "rank_creation_supply" if seed.rank_supply else None
        ),
        initial_fdv_usd=None,
        approx_peak_fdv_usd=None,
        peak_multiple=None,
        tiers=(),
        meets_peak_threshold=False,
        current_kols=seed.current_kols,
        max_kols=seed.max_kols,
        precision=precision,
        status=status,
        receipts=(trace.receipt,),
    )


def _validate_window(seed: TokenSeed, start: int, end_exclusive: int) -> None:
    if not 0 < start < end_exclusive or end_exclusive - start > 7 * 86_400:
        raise ValueError("market audit requires a positive window of at most seven days")
    if not start <= seed.created_at < end_exclusive:
        raise ValueError("token creation is outside the assigned market window")
