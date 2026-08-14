"""Pure point-in-time outcome rules for early-wallet qualification."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .models import Candle


@dataclass(frozen=True, slots=True)
class WalletBuyOutcome:
    mature_as_of_signal: bool
    measurable: bool
    hit: bool | None
    peak_price_usd: Decimal | None
    peak_fdv_usd: Decimal | None
    multiple: Decimal | None
    reasons: tuple[str, ...]


def assess_wallet_buy_outcome(
    *,
    buy_at: int,
    signal_at: int,
    buy_price_usd: Decimal | None,
    total_supply: Decimal | None,
    candles: Iterable[Candle],
    horizon_seconds: int = 86_400,
    interval_seconds: int = 300,
    minimum_multiple: Decimal = Decimal("2"),
    minimum_peak_fdv_usd: Decimal = Decimal("500000"),
) -> WalletBuyOutcome:
    """Measure only complete post-buy candles whose outcome existed at signal time."""

    if not 0 < buy_at < signal_at or horizon_seconds <= 0 or interval_seconds <= 0:
        raise ValueError("wallet outcome bounds are invalid")
    if minimum_multiple <= 1 or minimum_peak_fdv_usd <= 0:
        raise ValueError("wallet outcome thresholds are invalid")
    mature = buy_at + horizon_seconds <= signal_at
    if not mature:
        return _missing(False, "outcome_horizon_not_mature_as_of_signal")
    if buy_price_usd is None or buy_price_usd <= 0:
        return _missing(True, "buy_price_missing")
    if total_supply is None or total_supply <= 0:
        return _missing(True, "supply_missing")
    first_full_bar = ((buy_at + interval_seconds - 1) // interval_seconds) * interval_seconds
    end_exclusive = buy_at + horizon_seconds
    usable = tuple(
        candle for candle in candles
        if first_full_bar <= candle.time
        and candle.time + interval_seconds <= end_exclusive
    )
    if not usable:
        return _missing(True, "post_buy_market_history_missing")
    peak = max(item.high for item in usable)
    multiple = peak / buy_price_usd
    peak_fdv = peak * total_supply
    hit = multiple >= minimum_multiple and peak_fdv >= minimum_peak_fdv_usd
    return WalletBuyOutcome(
        mature_as_of_signal=True,
        measurable=True,
        hit=hit,
        peak_price_usd=peak,
        peak_fdv_usd=peak_fdv,
        multiple=multiple,
        reasons=("qualified_24h_pre_peak_hit",) if hit else ("outcome_threshold_not_met",),
    )


def _missing(mature: bool, reason: str) -> WalletBuyOutcome:
    return WalletBuyOutcome(
        mature_as_of_signal=mature,
        measurable=False,
        hit=None,
        peak_price_usd=None,
        peak_fdv_usd=None,
        multiple=None,
        reasons=(reason,),
    )
