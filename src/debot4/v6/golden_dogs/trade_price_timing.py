"""Pure transaction-price timing relative to a retrospective 1m baseline."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Iterable

from .gmgn_market_trades import GmgnMarketTrade


class TradeSignalStage(str, Enum):
    BEFORE_BASELINE_KNOWN = "before_baseline_known"
    STRICT_PRE_MOTION = "strict_pre_motion"
    CROSSING_SECOND_AMBIGUOUS = "crossing_second_ambiguous"
    AFTER_MOTION = "after_motion"
    MOTION_NOT_OBSERVED = "motion_not_observed"


@dataclass(frozen=True, slots=True)
class TransactionPriceCrossing:
    threshold_price_usd: Decimal
    occurred_at: int
    provider_sequence: int | None
    transaction_hash: str
    same_second_trade_count: int
    order_complete: bool


@dataclass(frozen=True, slots=True)
class TradeSignalTiming:
    stage: TradeSignalStage
    strict_advance: bool
    same_second_ambiguous: bool
    seconds_to_motion: int | None
    sequence_gap: int | None


def find_transaction_price_crossing(
    trades: Iterable[GmgnMarketTrade],
    threshold_price_usd: Decimal,
    *,
    not_before: int | None = None,
) -> TransactionPriceCrossing | None:
    """Find the first provider-ordered swap crossing after a known baseline."""

    if threshold_price_usd <= 0:
        raise ValueError("transaction crossing threshold must be positive")
    if not_before is not None and not_before <= 0:
        raise ValueError("transaction crossing start must be positive")
    swaps = tuple(sorted(
        (
            trade for trade in trades
            if trade.event in {"buy", "sell"} and trade.price_usd is not None
            and (not_before is None or trade.timestamp >= not_before)
        ),
        key=_order_key,
    ))
    crossed = next(
        (trade for trade in swaps if trade.price_usd >= threshold_price_usd),
        None,
    )
    if crossed is None:
        return None
    same_second = tuple(item for item in swaps if item.timestamp == crossed.timestamp)
    return TransactionPriceCrossing(
        threshold_price_usd=threshold_price_usd,
        occurred_at=crossed.timestamp,
        provider_sequence=crossed.provider_sequence,
        transaction_hash=crossed.transaction_hash,
        same_second_trade_count=len(same_second),
        order_complete=all(item.provider_sequence is not None for item in same_second),
    )


def classify_trade_signal(
    trade: GmgnMarketTrade,
    crossing: TransactionPriceCrossing | None,
    *,
    baseline_established_at: int,
) -> TradeSignalTiming:
    """Classify a buy while keeping same-second missing order explicitly unknown."""

    if trade.event != "buy":
        raise ValueError("only buys can be transaction-price signals")
    if baseline_established_at <= 0:
        raise ValueError("baseline establishment time must be positive")
    if trade.timestamp < baseline_established_at:
        stage = TradeSignalStage.BEFORE_BASELINE_KNOWN
    elif crossing is None:
        stage = TradeSignalStage.MOTION_NOT_OBSERVED
    elif strictly_precedes_crossing(
        trade.timestamp, trade.provider_sequence, crossing,
    ):
        stage = TradeSignalStage.STRICT_PRE_MOTION
    elif trade.timestamp > crossing.occurred_at:
        stage = TradeSignalStage.AFTER_MOTION
    elif _at_crossing_or_after(trade, crossing):
        stage = TradeSignalStage.AFTER_MOTION
    else:
        stage = TradeSignalStage.CROSSING_SECOND_AMBIGUOUS
    strict = stage == TradeSignalStage.STRICT_PRE_MOTION
    gap = None
    if trade.provider_sequence is not None and crossing is not None:
        if crossing.provider_sequence is not None:
            gap = crossing.provider_sequence - trade.provider_sequence
    return TradeSignalTiming(
        stage=stage,
        strict_advance=strict,
        same_second_ambiguous=stage == TradeSignalStage.CROSSING_SECOND_AMBIGUOUS,
        seconds_to_motion=(
            None if crossing is None else crossing.occurred_at - trade.timestamp
        ),
        sequence_gap=gap,
    )


def strictly_precedes_crossing(
    occurred_at: int,
    provider_sequence: int | None,
    crossing: TransactionPriceCrossing,
) -> bool:
    """Conservatively compare a serialized event with a price crossing."""

    if occurred_at <= 0:
        raise ValueError("event time must be positive")
    if occurred_at < crossing.occurred_at:
        return True
    if occurred_at > crossing.occurred_at:
        return False
    return (
        provider_sequence is not None
        and crossing.provider_sequence is not None
        and crossing.order_complete
        and provider_sequence < crossing.provider_sequence
    )


def _at_crossing_or_after(
    trade: GmgnMarketTrade, crossing: TransactionPriceCrossing,
) -> bool:
    return (
        trade.provider_sequence is not None
        and crossing.provider_sequence is not None
        and crossing.order_complete
        and trade.provider_sequence >= crossing.provider_sequence
    )


def _order_key(trade: GmgnMarketTrade) -> tuple[int, bool, int, str]:
    return (
        trade.timestamp,
        trade.provider_sequence is None,
        trade.provider_sequence or 0,
        trade.transaction_hash,
    )
