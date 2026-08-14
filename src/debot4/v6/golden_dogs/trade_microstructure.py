"""Pure price-ladder and pre-motion buy-flow measurements."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from .gmgn_market_trades import GmgnMarketTrade
from .trade_price_timing import (
    TransactionPriceCrossing,
    classify_trade_signal,
    find_transaction_price_crossing,
)


PRICE_LADDER_MULTIPLES = (
    Decimal("1.02"),
    Decimal("1.05"),
    Decimal("1.10"),
    Decimal("1.20"),
)
FLOW_WINDOWS_SECONDS = (15, 30, 60, 120, 300)


@dataclass(frozen=True, slots=True)
class PriceLadderStep:
    multiple: Decimal
    crossing: TransactionPriceCrossing | None


@dataclass(frozen=True, slots=True)
class BuyFlowSnapshot:
    window_seconds: int | None
    start_at: int
    end_at: int
    buy_count: int
    unique_wallet_count: int
    gross_buy_usd: Decimal
    repeat_wallet_count: int
    burst_wallet_count: int
    largest_wallet_buy_count: int
    largest_wallet_gross_buy_usd: Decimal


def find_price_ladder(
    trades: Iterable[GmgnMarketTrade],
    baseline_price_usd: Decimal,
    *,
    baseline_established_at: int,
    multiples: tuple[Decimal, ...] = PRICE_LADDER_MULTIPLES,
) -> tuple[PriceLadderStep, ...]:
    """Find provider-ordered swap crossings from the known baseline onward."""

    if baseline_price_usd <= 0 or baseline_established_at <= 0:
        raise ValueError("price ladder baseline must be positive")
    if (
        not multiples
        or any(value <= 1 for value in multiples)
        or tuple(sorted(set(multiples))) != multiples
    ):
        raise ValueError("price ladder multiples must be unique and increasing")
    rows = tuple(trades)
    return tuple(
        PriceLadderStep(
            multiple,
            find_transaction_price_crossing(
                rows,
                baseline_price_usd * multiple,
                not_before=baseline_established_at,
            ),
        )
        for multiple in multiples
    )


def summarize_pre_crossing_buy_flow(
    trades: Iterable[GmgnMarketTrade],
    crossing: TransactionPriceCrossing,
    *,
    baseline_established_at: int,
    windows_seconds: tuple[int, ...] = FLOW_WINDOWS_SECONDS,
    burst_seconds: int = 60,
    burst_minimum_buys: int = 3,
) -> tuple[BuyFlowSnapshot, ...]:
    """Summarize only buys whose provider order is strictly before crossing."""

    if baseline_established_at <= 0 or baseline_established_at > crossing.occurred_at:
        raise ValueError("buy-flow baseline must not follow the crossing")
    if (
        any(value <= 0 for value in windows_seconds)
        or tuple(sorted(set(windows_seconds))) != windows_seconds
        or burst_seconds <= 0
        or burst_minimum_buys < 2
    ):
        raise ValueError("invalid buy-flow windows or burst rule")
    eligible = tuple(
        trade for trade in trades
        if trade.event == "buy"
        and classify_trade_signal(
            trade, crossing, baseline_established_at=baseline_established_at,
        ).strict_advance
    )
    snapshots = [
        _snapshot(
            eligible,
            max(baseline_established_at, crossing.occurred_at - window),
            crossing.occurred_at,
            window,
            burst_seconds,
            burst_minimum_buys,
        )
        for window in windows_seconds
    ]
    snapshots.append(_snapshot(
        eligible,
        baseline_established_at,
        crossing.occurred_at,
        None,
        burst_seconds,
        burst_minimum_buys,
    ))
    return tuple(snapshots)


def _snapshot(
    trades: tuple[GmgnMarketTrade, ...],
    start_at: int,
    end_at: int,
    window_seconds: int | None,
    burst_seconds: int,
    burst_minimum_buys: int,
) -> BuyFlowSnapshot:
    rows = tuple(trade for trade in trades if trade.timestamp >= start_at)
    wallets: dict[str, list[GmgnMarketTrade]] = {}
    for trade in rows:
        wallets.setdefault(trade.wallet, []).append(trade)
    counts = tuple(len(items) for items in wallets.values())
    totals = tuple(
        sum((item.amount_usd or Decimal(0) for item in items), Decimal(0))
        for items in wallets.values()
    )
    return BuyFlowSnapshot(
        window_seconds=window_seconds,
        start_at=start_at,
        end_at=end_at,
        buy_count=len(rows),
        unique_wallet_count=len(wallets),
        gross_buy_usd=sum((item.amount_usd or Decimal(0) for item in rows), Decimal(0)),
        repeat_wallet_count=sum(value >= 2 for value in counts),
        burst_wallet_count=sum(
            _has_burst(items, burst_seconds, burst_minimum_buys)
            for items in wallets.values()
        ),
        largest_wallet_buy_count=max(counts, default=0),
        largest_wallet_gross_buy_usd=max(totals, default=Decimal(0)),
    )


def _has_burst(
    trades: list[GmgnMarketTrade], seconds: int, minimum: int,
) -> bool:
    times = sorted(item.timestamp for item in trades)
    left = 0
    for right, occurred_at in enumerate(times):
        while occurred_at - times[left] > seconds:
            left += 1
        if right - left + 1 >= minimum:
            return True
    return False
